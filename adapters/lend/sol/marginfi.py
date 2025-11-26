from adapters.lend.abstract import LendingAdapter


class MarginfiAdapter:
    name = "marginfi"
    chain = "sol"

    def fetch_positions(self, wallet: str):
        raise NotImplementedError("Marginfi adapter not implemented yet.")

    def snapshot(self, wallet: str):
        return self.fetch_positions(wallet)
