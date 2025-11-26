from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class LPAdapter(Protocol):
    """
    Abstract LP adapter for AMM/CLMM protocols.
    """

    name: str
    chain: str

    def fetch_position(self, wallet: str) -> Dict[str, Any]:
        ...

    def snapshot(self, wallet: str) -> Dict[str, Any]:
        ...
