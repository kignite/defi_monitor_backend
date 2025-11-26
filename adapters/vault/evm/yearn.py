from adapters.vault.abstract import VaultAdapter


class YearnAdapter:
    name = "yearn"
    chain = "evm"

    def onchain_snapshot(self, cfg, user_cfg):
        raise NotImplementedError("Yearn adapter not implemented yet.")

    def offchain_snapshot(self, cfg, user_cfg):
        raise NotImplementedError("Yearn adapter not implemented yet.")

    def list_token_accounts(self, cfg):
        raise NotImplementedError("Yearn adapter not implemented yet.")
