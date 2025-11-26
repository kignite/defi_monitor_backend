from adapters.lp.abstract import LPAdapter


class OrcaWhirlpoolAdapter:
    name = "orca_whirlpool"
    chain = "sol"

    def fetch_position(self, wallet: str):
        raise NotImplementedError("Orca Whirlpool adapter not implemented yet.")

    def snapshot(self, wallet: str):
        return self.fetch_position(wallet)
