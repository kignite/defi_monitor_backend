from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class VaultAdapter(Protocol):
    """
    Adapter interface for vault / structured product protocols.
    """

    name: str

    def onchain_snapshot(self, cfg: Any, user_cfg: Any) -> Dict[str, Any]:  # cfg types injected at runtime
        ...

    def offchain_snapshot(self, cfg: Any, user_cfg: Any) -> Dict[str, Any]:
        ...

    def list_token_accounts(self, cfg: Any) -> Dict[str, Any] | list[Dict[str, Any]]:
        ...
