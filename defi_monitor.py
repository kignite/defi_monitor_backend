import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from adapters.vault.abstract import VaultAdapter
from adapters.vault.voltr import VoltrAdapter


@dataclass
class VaultConfig:
    """Static configuration for a single vault."""

    vault_pubkey: str
    lp_mint: str
    idle_usdc_ata: str
    usdc_mint: str
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    voltr_api_base: str = "https://api.voltr.xyz"


@dataclass
class UserConfig:
    """User-scoped inputs."""

    wallet: str
    lp_token_account: str


class VoltrVaultMonitor:
    """
    Light abstraction around the existing investigation scripts.

    - Uses an adapter so different protocols can plug in their own logic.
    - Provides snapshot() with a unified return shape.
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        adapter: Optional[VaultAdapter] = None,
    ) -> None:
        session = session or requests.Session()
        self.adapter = adapter or VoltrAdapter(session=session)

    # --- Unified snapshot ---
    def snapshot(self, cfg: VaultConfig, user_cfg: UserConfig, include_token_accounts: bool = False) -> Dict[str, Any]:
        """
        Return a single dict consumable by the defi monitor.

        Shape:
          {
            "timestamp": "...",
            "vault": {...},
            "user": {...},
            "sources": {
              "onchain_idle": {"ok": bool, "data": {...} | None, "error": str | None},
              "voltr_api": {"ok": bool, "data": {...} | None, "error": str | None}
            },
            "debug": {...} # optional
          }
        """
        onchain = {"ok": False, "data": None, "error": None}
        offchain = {"ok": False, "data": None, "error": None}
        debug: Dict[str, Any] = {}

        try:
            onchain = self.adapter.onchain_snapshot(cfg, user_cfg)
        except Exception as exc:  # noqa: BLE001 - we want to capture and return the error
            onchain = {"ok": False, "data": None, "error": str(exc)}

        try:
            offchain = self.adapter.offchain_snapshot(cfg, user_cfg)
        except Exception as exc:  # noqa: BLE001
            offchain = {"ok": False, "data": None, "error": str(exc)}

        if include_token_accounts:
            try:
                debug["token_accounts"] = self.adapter.list_token_accounts(cfg)
            except Exception as exc:  # noqa: BLE001
                debug["token_accounts_error"] = str(exc)

        snapshot = {
            "timestamp": int(time.time()),
            "vault": {
                "pubkey": cfg.vault_pubkey,
                "lp_mint": cfg.lp_mint,
                "idle_usdc_ata": cfg.idle_usdc_ata,
                "usdc_mint": cfg.usdc_mint,
            },
            "user": {
                "wallet": user_cfg.wallet,
                "lp_token_account": user_cfg.lp_token_account,
            },
            "sources": {
                "onchain_idle": onchain,
                "offchain": offchain,
            },
            "meta": {
                "rpc_url": cfg.rpc_url,
                "voltr_api_base": cfg.voltr_api_base,
                "adapter": getattr(self.adapter, "name", "unknown"),
            },
        }

        if debug:
            snapshot["debug"] = debug

        return snapshot


# Example usage (kept minimal; do not run network calls on import)
if __name__ == "__main__":
    vault_cfg = VaultConfig(
        vault_pubkey="FajosXiYhqUDZ9cEB3pwS8n8pvcAbL3KzCGZnWDNvgLa",
        lp_mint="A5dvM5NKnuo6tmwoiEFC22qcXcUsa6mUoUtpkxjm1gKg",
        idle_usdc_ata="3AK6wAysksFRke6KJasnnL1sFn73jqhwDNquR2WhgrhE",
        usdc_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    )
    user_cfg = UserConfig(
        wallet="51pijqibmHQ17GZWjV8g8AyFWx1ZMmkUDtFR4Vz8Ah3F",
        lp_token_account="BKCANLpd7r1k1dkki4Wj48kJZXd7CFFEzNnZXQGTrMk1",
    )

    monitor = VoltrVaultMonitor()
    result = monitor.snapshot(vault_cfg, user_cfg, include_token_accounts=True)
    print(result)
