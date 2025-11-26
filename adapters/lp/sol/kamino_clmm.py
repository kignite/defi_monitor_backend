from adapters.lp.abstract import LPAdapter


class KaminoCLMMAdapter:
    name = "kamino_clmm"
    chain = "sol"

    def fetch_position(self, wallet: str):
        raise NotImplementedError("Kamino CLMM adapter not implemented yet.")

    def snapshot(self, wallet: str):
        return self.fetch_position(wallet)
