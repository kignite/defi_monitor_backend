from typing import Any, Dict, List, Optional

import requests

# Avoid direct import cycle on type checking
try:
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:  # pragma: no cover
        from defi_monitor import VaultConfig, UserConfig
except Exception:
    TYPE_CHECKING = False


class VoltrAdapter:
    """
    Voltr-specific adapter that encapsulates RPC + Voltr REST behaviors.
    """

    name = "voltr"

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    # --- RPC helpers ---
    def _rpc(self, cfg: "VaultConfig", method: str, params: List[Any]) -> Dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        resp = self.session.post(cfg.rpc_url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data

    def _get_account_info(self, cfg: "VaultConfig", address: str, encoding: str = "base64") -> Optional[Dict[str, Any]]:
        resp = self._rpc(cfg, "getAccountInfo", [address, {"encoding": encoding}])
        return resp.get("result", {}).get("value")

    def _get_token_balance(self, cfg: "VaultConfig", token_account: str) -> float:
        resp = self._rpc(cfg, "getTokenAccountBalance", [token_account])
        value = resp.get("result", {}).get("value")
        if not value:
            return 0.0
        return float(value.get("uiAmount", 0.0))

    def _get_token_supply(self, cfg: "VaultConfig", mint: str) -> float:
        resp = self._rpc(cfg, "getTokenSupply", [mint])
        value = resp.get("result", {}).get("value")
        if not value:
            return 0.0
        return float(value.get("uiAmount", 0.0))

    def _get_token_accounts_by_owner(self, cfg: "VaultConfig", owner: str) -> List[Dict[str, Any]]:
        resp = self._rpc(
            cfg,
            "getTokenAccountsByOwner",
            [
                owner,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ],
        )
        return resp.get("result", {}).get("value", [])

    # --- Voltr specifics ---
    def _get_vault_idle_usdc(self, cfg: "VaultConfig") -> float:
        return self._get_token_balance(cfg, cfg.idle_usdc_ata)

    def _get_user_lp_amount(self, cfg: "VaultConfig", user_cfg: "UserConfig") -> float:
        return self._get_token_balance(cfg, user_cfg.lp_token_account)

    def onchain_snapshot(self, cfg: "VaultConfig", user_cfg: "UserConfig") -> Dict[str, Any]:
        vault_nav_idle = self._get_vault_idle_usdc(cfg)
        lp_supply = self._get_token_supply(cfg, cfg.lp_mint)
        user_lp = self._get_user_lp_amount(cfg, user_cfg)

        lp_price_idle = (vault_nav_idle / lp_supply) if lp_supply > 0 else 0.0
        share_idle = (user_lp / lp_supply) if lp_supply > 0 else 0.0
        withdrawable_idle = user_lp * lp_price_idle
        idle_ratio = (vault_nav_idle / vault_nav_idle) if vault_nav_idle else 0.0

        return {
            "ok": True,
            "data": {
                "vault_nav_idle": vault_nav_idle,
                "lp_supply": lp_supply,
                "user_lp": user_lp,
                "lp_price_idle": lp_price_idle,
                "share_idle": share_idle,
                "withdrawable_idle": withdrawable_idle,
                "idle_ratio": idle_ratio,
            },
            "error": None,
        }

    def _get_voltr_user_balance_raw(self, cfg: "VaultConfig", user_cfg: "UserConfig") -> Dict[str, Any]:
        url = f"{cfg.voltr_api_base}/vault/{cfg.vault_pubkey}/user/{user_cfg.wallet}/balance"
        resp = self.session.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def offchain_snapshot(self, cfg: "VaultConfig", user_cfg: "UserConfig") -> Dict[str, Any]:
        raw = self._get_voltr_user_balance_raw(cfg, user_cfg)
        if not raw.get("success"):
            raise RuntimeError(f"Voltr API returned error: {raw}")

        user_asset_amount = raw["data"]["userAssetAmount"]
        withdrawable_usdc = user_asset_amount / 1_000_000

        return {
            "ok": True,
            "data": {
                "withdrawable_usdc": withdrawable_usdc,
                "raw": raw,
            },
            "error": None,
        }

    def _get_vault_token_authority(self, cfg: "VaultConfig") -> str:
        info = self._get_account_info(cfg, cfg.idle_usdc_ata, encoding="jsonParsed")
        if not info:
            raise RuntimeError("Idle USDC ATA not found.")
        parsed = info["data"]["parsed"]
        owner = parsed["info"]["owner"]
        return owner

    def list_token_accounts(self, cfg: "VaultConfig") -> List[Dict[str, Any]]:
        authority = self._get_vault_token_authority(cfg)
        accounts = self._get_token_accounts_by_owner(cfg, authority)

        normalized: List[Dict[str, Any]] = []
        for acc in accounts:
            pubkey = acc.get("pubkey")
            data = acc.get("account", {}).get("data", {})
            parsed = data.get("parsed", {})
            info = parsed.get("info", {})
            token_amount = info.get("tokenAmount", {})

            normalized.append(
                {
                    "pubkey": pubkey,
                    "mint": info.get("mint"),
                    "amount": token_amount.get("uiAmount"),
                    "decimals": token_amount.get("decimals"),
                }
            )

        return normalized
