from adapters.lp.abstract import LPAdapter


class UniswapV3Adapter:
    name = "uniswap_v3"
    chain = "evm"

    def fetch_position(self, wallet: str):
        raise NotImplementedError("Uniswap v3 adapter not implemented yet.")

    def snapshot(self, wallet: str):
        return self.fetch_position(wallet)
