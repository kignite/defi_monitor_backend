from adapters.lend.abstract import LendingAdapter


class SolendAdapter:
    name = "solend"
    chain = "sol"

    def fetch_positions(self, wallet: str):
        raise NotImplementedError("Solend adapter not implemented yet.")

    def snapshot(self, wallet: str):
        return self.fetch_positions(wallet)
