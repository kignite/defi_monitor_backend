from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class LendingAdapter(Protocol):
    """
    Abstract lending adapter.
    Concrete implementations should provide protocol/chain metadata and data fetchers.
    """

    name: str
    chain: str

    def fetch_positions(self, wallet: str) -> Dict[str, Any]:
        ...

    def snapshot(self, wallet: str) -> Dict[str, Any]:
        """Optional richer snapshot wrapper."""
        ...
