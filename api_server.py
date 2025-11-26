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
from vault_adapter import VaultAdapter, VoltrAdapter


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
    return snap


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
    return monitor.snapshot(vault_cfg, user_cfg, include_token_accounts=payload.include_token_accounts)


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

    return monitor.snapshot(vault_cfg, user_cfg, include_token_accounts=include_token_accounts)
