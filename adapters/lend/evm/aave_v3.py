from adapters.lend.abstract import LendingAdapter


class AaveV3Adapter:
    name = "aave_v3"
    chain = "evm"

    def fetch_positions(self, wallet: str):
        raise NotImplementedError("Aave v3 adapter not implemented yet.")

    def snapshot(self, wallet: str):
        return self.fetch_positions(wallet)
