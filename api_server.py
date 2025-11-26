"""
Minimal API server wiring the monitor into HTTP endpoints.

Usage:
  pip install fastapi uvicorn
  uvicorn api_server:app --reload --port 8000
"""

from typing import Dict

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


session = requests.Session()

# Adapter registry; extend this dict when adding new protocols.
ADAPTERS: Dict[str, VaultAdapter] = {
    "voltr": VoltrAdapter(session=session),
}

app = FastAPI(title="Defi Monitor API", version="0.1.0")


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


# Optional convenience: GET endpoint using the built-in demo config
@app.get("/snapshot/default")
def snapshot_default(include_token_accounts: bool = False) -> Dict[str, object]:
    demo_payload = SnapshotRequest(
        vault_pubkey="FajosXiYhqUDZ9cEB3pwS8n8pvcAbL3KzCGZnWDNvgLa",
        lp_mint="A5dvM5NKnuo6tmwoiEFC22qcXcUsa6mUoUtpkxjm1gKg",
        idle_usdc_ata="3AK6wAysksFRke6KJasnnL1sFn73jqhwDNquR2WhgrhE",
        usdc_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        wallet="51pijqibmHQ17GZWjV8g8AyFWx1ZMmkUDtFR4Vz8Ah3F",
        lp_token_account="BKCANLpd7r1k1dkki4Wj48kJZXd7CFFEzNnZXQGTrMk1",
        include_token_accounts=include_token_accounts,
    )
    return snapshot(demo_payload)
