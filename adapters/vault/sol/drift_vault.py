from adapters.vault.abstract import VaultAdapter


class DriftVaultAdapter:
    name = "drift_vault"
    chain = "sol"

    def onchain_snapshot(self, cfg, user_cfg):
        raise NotImplementedError("Drift vault adapter not implemented yet.")

    def offchain_snapshot(self, cfg, user_cfg):
        raise NotImplementedError("Drift vault adapter not implemented yet.")

    def list_token_accounts(self, cfg):
        raise NotImplementedError("Drift vault adapter not implemented yet.")
