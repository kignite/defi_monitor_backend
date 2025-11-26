"""
Minimal API server wiring the monitor into HTTP endpoints.

Usage:
  pip install fastapi uvicorn requests
  uvicorn api_server:app --reload --port 8000
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from defi_monitor import VaultConfig, UserConfig, VoltrVaultMonitor
from adapters.vault.abstract import VaultAdapter
from adapters.vault.voltr import VoltrAdapter
from risk.risk_factory import evaluate as evaluate_risk_model


class SnapshotRequest(BaseModel):
    adapter: str = Field(default="voltr", description="Which adapter to use (default: voltr).")
    vault_pubkey: str
    lp_mint: str
    idle_usdc_ata: str
    usdc_mint: str
    wallet: str
    lp_token_account: str
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    voltr_api_base: str = "https://api.voltr.xyz"
    include_token_accounts: bool = False


class MonitorRequest(BaseModel):
    """
    Minimal request shape for frontends: only protocol + user address.
    Vault config comes from server-side registry.
    lp_token_account is optional (fallback to registry default if present).
    """

    protocol: str = Field(default="voltr", description="Protocol/adapter name.")
    user_wallet: str = Field(..., description="User wallet address.")
    vault_id: Optional[str] = Field(default=None, description="Vault identifier (protocol-specific).")
    lp_token_account: Optional[str] = Field(default=None, description="User LP token account; optional.")
    include_token_accounts: bool = False


session = requests.Session()

# Adapter registry; extend this dict when adding new protocols.
ADAPTERS: Dict[str, VaultAdapter] = {
    "voltr": VoltrAdapter(session=session),
}

app = FastAPI(title="Defi Monitor API", version="0.1.0")

HARD_LIMIT_MULTIPLIER = 50
SOFT_LIMIT_MULTIPLIER = 200


def evaluate_risk_status(utilization: float, available: float, balance_value: float) -> Dict[str, object]:
    """
    Mirror the frontend risk rules to keep consistent UX:
      rule1Hard: available < balance * HARD_LIMIT_MULTIPLIER
      rule2Soft: available < balance * SOFT_LIMIT_MULTIPLIER
      rule3Hard: utilization > 95%
      rule4Soft: utilization > 90%
    """
    rule1Hard = available < balance_value * HARD_LIMIT_MULTIPLIER
    rule2Soft = available < balance_value * SOFT_LIMIT_MULTIPLIER
    rule3Hard = utilization > 95
    rule4Soft = utilization > 90

    if rule1Hard and rule3Hard:
        return {
            "code": "critical13",
            "label": "Critical 1+3",
            "badge": "1+3",
            "tooltip": "Rules 1 + 3: available < balance x 50 and utilization > 95% at the same time.",
            "conditions": {"rule1Hard": rule1Hard, "rule2Soft": rule2Soft, "rule3Hard": rule3Hard, "rule4Soft": rule4Soft},
        }
    if rule1Hard:
        return {
            "code": "critical1",
            "label": "Critical 1",
            "badge": "1",
            "tooltip": "Rule 1 (hard liquidity): available < balance x 50. Exit is highly constrained.",
            "conditions": {"rule1Hard": rule1Hard, "rule2Soft": rule2Soft, "rule3Hard": rule3Hard, "rule4Soft": rule4Soft},
        }
    if rule2Soft:
        return {
            "code": "warning2",
            "label": "Warning 2",
            "badge": "2",
            "tooltip": "Rule 2 (soft liquidity): available < balance x 200. Monitor exit liquidity.",
            "conditions": {"rule1Hard": rule1Hard, "rule2Soft": rule2Soft, "rule3Hard": rule3Hard, "rule4Soft": rule4Soft},
        }
    if rule3Hard:
        return {
            "code": "warning3",
            "label": "Warning 3",
            "badge": "3",
            "tooltip": "Rule 3 (hard utilization): utilization > 95%; lending is crowded.",
            "conditions": {"rule1Hard": rule1Hard, "rule2Soft": rule2Soft, "rule3Hard": rule3Hard, "rule4Soft": rule4Soft},
        }
    if rule4Soft:
        return {
            "code": "warning4",
            "label": "Warning 4",
            "badge": "4",
            "tooltip": "Rule 4 (soft utilization): utilization > 90%; approaching congestion.",
            "conditions": {"rule1Hard": rule1Hard, "rule2Soft": rule2Soft, "rule3Hard": rule3Hard, "rule4Soft": rule4Soft},
        }

    return {
        "code": "ok",
        "label": "Low",
        "badge": "",
        "tooltip": "No risk rules triggered.",
        "conditions": {"rule1Hard": rule1Hard, "rule2Soft": rule2Soft, "rule3Hard": rule3Hard, "rule4Soft": rule4Soft},
    }

def load_registry() -> Dict[str, Dict[Optional[str], Dict[str, str]]]:
    """
    Load vault registry from JSON. Falls back to inline defaults if file missing/invalid.
    Allows overriding path via VAULT_CONFIG_PATH.
    """
    default_registry: Dict[str, Dict[Optional[str], Dict[str, str]]] = {}

    # Inline fallback using prior defaults
    fallback_vault_cfg = VaultConfig(
        vault_pubkey=os.getenv("VAULT_PUBKEY", "FajosXiYhqUDZ9cEB3pwS8n8pvcAbL3KzCGZnWDNvgLa"),
        lp_mint=os.getenv("VAULT_LP_MINT", "A5dvM5NKnuo6tmwoiEFC22qcXcUsa6mUoUtpkxjm1gKg"),
        idle_usdc_ata=os.getenv("VAULT_IDLE_USDC_ATA", "3AK6wAysksFRke6KJasnnL1sFn73jqhwDNquR2WhgrhE"),
        usdc_mint=os.getenv("USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
        rpc_url=os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com"),
        voltr_api_base=os.getenv("VOLTR_API_BASE", "https://api.voltr.xyz"),
    )
    fallback_user_cfg = UserConfig(
        wallet=os.getenv("USER_WALLET", "51pijqibmHQ17GZWjV8g8AyFWx1ZMmkUDtFR4Vz8Ah3F"),
        lp_token_account=os.getenv("USER_LP_ATA", "BKCANLpd7r1k1dkki4Wj48kJZXd7CFFEzNnZXQGTrMk1"),
    )
    default_registry = {
        "voltr": {
            "default": {
                "vault_pubkey": fallback_vault_cfg.vault_pubkey,
                "lp_mint": fallback_vault_cfg.lp_mint,
                "idle_usdc_ata": fallback_vault_cfg.idle_usdc_ata,
                "usdc_mint": fallback_vault_cfg.usdc_mint,
                "rpc_url": fallback_vault_cfg.rpc_url,
                "voltr_api_base": fallback_vault_cfg.voltr_api_base,
                "default_lp_token_account": fallback_user_cfg.lp_token_account,
            }
        }
    }

    path = Path(os.getenv("VAULT_CONFIG_PATH", "config/vaults.json"))
    try:
        raw = json.loads(path.read_text())
        # Basic validation shape
        if not isinstance(raw, dict):
            raise ValueError("vaults.json must be an object at root")
        return raw  # type: ignore[return-value]
    except Exception:
        return default_registry


VAULT_REGISTRY: Dict[str, Dict[Optional[str], Dict[str, str]]] = load_registry()


def resolve_adapter(name: str) -> VaultAdapter:
    adapter = ADAPTERS.get(name.lower())
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Unknown adapter '{name}'. Available: {list(ADAPTERS)}")
    return adapter


def attach_summary(snapshot: Dict[str, object], vault_cfg_raw: Dict[str, str], adapter_name: str) -> Dict[str, object]:
    """
    Guarantee UI-friendly fields are present (name, chain, risk, balance, totalLiquidity, borrowed, myDeposit).
    """
    sources = snapshot.get("sources", {}) if isinstance(snapshot, dict) else {}
    onchain = sources.get("onchain_idle", {}) if isinstance(sources, dict) else {}
    offchain = sources.get("offchain", {}) if isinstance(sources, dict) else {}

    onchain_data = onchain.get("data") if isinstance(onchain, dict) else None
    offchain_data = offchain.get("data") if isinstance(offchain, dict) else None

    vault_nav_idle = 0.0
    user_lp = 0.0
    withdrawable = 0.0

    if isinstance(onchain_data, dict):
        vault_nav_idle = float(onchain_data.get("vault_nav_idle", 0.0) or 0.0)
        user_lp = float(onchain_data.get("user_lp", 0.0) or 0.0)
    if isinstance(offchain_data, dict):
        withdrawable = float(offchain_data.get("withdrawable_usdc", 0.0) or 0.0)

    display_name = vault_cfg_raw.get("display_name") or vault_cfg_raw.get("name") or f"{adapter_name} vault"
    chain = vault_cfg_raw.get("chain") or "UNKNOWN"
    balance_value = withdrawable if withdrawable else vault_nav_idle or user_lp

    borrowed = float(vault_cfg_raw.get("borrowed", 0.0) or 0.0)
    total_liquidity = vault_nav_idle or borrowed  # fallback to avoid div by zero
    available = max(total_liquidity - borrowed, 0.0)
    utilization = (borrowed / total_liquidity * 100) if total_liquidity else 0.0
    risk_status = evaluate_risk_status(utilization=utilization, available=available, balance_value=balance_value)
    protocol_type = vault_cfg_raw.get("type", "vault")
    risk_model = evaluate_risk_model(
        protocol_type,
        {
            "utilization": utilization,
            "available": available,
            "balance_value": balance_value,
            "idle_ratio": idle_ratio,
            "deployment_rate": deployment_rate,
        },
    )

    summary = {
        "name": display_name,
        "chain": chain,
        "risk": risk_status.get("label", "UNKNOWN"),
        "balance": f"${withdrawable:,.2f}",
        "totalLiquidity": total_liquidity,
        "borrowed": borrowed,
        "myDeposit": user_lp,
        "riskStatus": risk_status,
        "riskModel": risk_model,
    }

    snapshot["summary"] = summary
    return snapshot


@app.get("/health")
def health() -> Dict[str, object]:
    return {
        "ok": True,
        "adapters": list(ADAPTERS.keys()),
        "vaults": {proto: list(vaults.keys()) for proto, vaults in VAULT_REGISTRY.items()},
    }


@app.post("/snapshot")
def snapshot(payload: SnapshotRequest) -> Dict[str, object]:
    adapter = resolve_adapter(payload.adapter)
    monitor = VoltrVaultMonitor(session=session, adapter=adapter)

    vault_cfg = VaultConfig(
        vault_pubkey=payload.vault_pubkey,
        lp_mint=payload.lp_mint,
        idle_usdc_ata=payload.idle_usdc_ata,
        usdc_mint=payload.usdc_mint,
        rpc_url=payload.rpc_url,
        voltr_api_base=payload.voltr_api_base,
    )
    user_cfg = UserConfig(wallet=payload.wallet, lp_token_account=payload.lp_token_account)

    snap = monitor.snapshot(vault_cfg, user_cfg, include_token_accounts=payload.include_token_accounts)
    return attach_summary(snap, vault_cfg_raw, adapter_name=payload.adapter)


# Frontend-friendly: use server-side registry; client only sends protocol + user.
@app.post("/monitor")
def monitor_endpoint(payload: MonitorRequest) -> Dict[str, object]:
    adapter = resolve_adapter(payload.protocol)
    vaults_for_proto = VAULT_REGISTRY.get(payload.protocol, {})
    vault_cfg_raw = vaults_for_proto.get(payload.vault_id)
    if not vault_cfg_raw:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown vault for protocol '{payload.protocol}' and vault_id '{payload.vault_id}'. Available: {list(vaults_for_proto.keys())}",
        )

    vault_cfg = VaultConfig(
        vault_pubkey=vault_cfg_raw["vault_pubkey"],
        lp_mint=vault_cfg_raw["lp_mint"],
        idle_usdc_ata=vault_cfg_raw["idle_usdc_ata"],
        usdc_mint=vault_cfg_raw["usdc_mint"],
        rpc_url=vault_cfg_raw["rpc_url"],
        voltr_api_base=vault_cfg_raw["voltr_api_base"],
    )

    lp_token_account = payload.lp_token_account or vault_cfg_raw.get("default_lp_token_account")
    if not lp_token_account:
        raise HTTPException(status_code=400, detail="lp_token_account is required for this protocol.")

    user_cfg = UserConfig(wallet=payload.user_wallet, lp_token_account=lp_token_account)
    monitor = VoltrVaultMonitor(session=session, adapter=adapter)
    snap = monitor.snapshot(vault_cfg, user_cfg, include_token_accounts=payload.include_token_accounts)
    return attach_summary(snap, vault_cfg_raw, adapter_name=payload.protocol)


# Convenience: GET endpoint using server defaults (env-driven)
@app.get("/snapshot")
def snapshot_default(include_token_accounts: bool = False, adapter: str = "voltr") -> Dict[str, object]:
    adapter_obj = resolve_adapter(adapter)
    monitor = VoltrVaultMonitor(session=session, adapter=adapter_obj)
    # Use registry default for the adapter if available
    vaults_for_proto = VAULT_REGISTRY.get(adapter, {})
    vault_cfg_raw = vaults_for_proto.get("default")
    if not vault_cfg_raw:
        raise HTTPException(status_code=400, detail=f"No default vault configured for adapter '{adapter}'.")

    vault_cfg = VaultConfig(
        vault_pubkey=vault_cfg_raw["vault_pubkey"],
        lp_mint=vault_cfg_raw["lp_mint"],
        idle_usdc_ata=vault_cfg_raw["idle_usdc_ata"],
        usdc_mint=vault_cfg_raw["usdc_mint"],
        rpc_url=vault_cfg_raw["rpc_url"],
        voltr_api_base=vault_cfg_raw["voltr_api_base"],
    )
    user_cfg = UserConfig(
        wallet=vault_cfg_raw.get("default_user_wallet", "51pijqibmHQ17GZWjV8g8AyFWx1ZMmkUDtFR4Vz8Ah3F"),
        lp_token_account=vault_cfg_raw.get("default_lp_token_account", "BKCANLpd7r1k1dkki4Wj48kJZXd7CFFEzNnZXQGTrMk1"),
    )

    snap = monitor.snapshot(vault_cfg, user_cfg, include_token_accounts=include_token_accounts)
    return attach_summary(snap, vault_cfg_raw, adapter_name=adapter)
