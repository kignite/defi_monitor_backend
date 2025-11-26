from adapters.lend.abstract import LendingAdapter


class MorphoAdapter:
    name = "morpho"
    chain = "evm"

    def fetch_positions(self, wallet: str):
        raise NotImplementedError("Morpho adapter not implemented yet.")

    def snapshot(self, wallet: str):
        return self.fetch_positions(wallet)
