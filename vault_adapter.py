# Backward-compatible shim; prefer adapters.vault.abstract / adapters.vault.voltr
from adapters.vault.abstract import VaultAdapter  # noqa: F401
from adapters.vault.voltr import VoltrAdapter  # noqa: F401
