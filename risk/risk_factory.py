from typing import Dict

from . import lending_rules, lp_rules, vault_rules


def evaluate(protocol_type: str, metrics: Dict[str, float]) -> Dict[str, object]:
    """
    Dispatch to protocol-specific risk model.
    """
    proto = (protocol_type or "").lower()
    if proto in ("lending", "lend", "money-market"):
        return lending_rules.evaluate(metrics)
    if proto in ("lp", "amm", "pool"):
        return lp_rules.evaluate(metrics)
    # default to vault model
    return vault_rules.evaluate(metrics)
