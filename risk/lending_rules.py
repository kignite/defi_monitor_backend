from typing import Dict, List

HARD_LIMIT_MULTIPLIER = 50
SOFT_LIMIT_MULTIPLIER = 200


def evaluate(metrics: Dict[str, float]) -> Dict[str, object]:
    """
    Lending risk model using utilization/liquidity checks.

    Expected metrics:
      utilization: percent (0-100)
      available: liquidity available
      balance_value: user balance value (for liquidity rules)
    """
    utilization = float(metrics.get("utilization", 0.0) or 0.0)
    available = float(metrics.get("available", 0.0) or 0.0)
    balance_value = float(metrics.get("balance_value", 0.0) or 0.0)

    rule1Hard = available < balance_value * HARD_LIMIT_MULTIPLIER
    rule2Soft = available < balance_value * SOFT_LIMIT_MULTIPLIER
    rule3Hard = utilization > 95
    rule4Soft = utilization > 90

    reasons: List[str] = []
    level = "ok"

    if rule1Hard and rule3Hard:
        level = "hard"
        reasons.append("available < balance x50 and utilization >95%")
    elif rule1Hard or rule3Hard:
        level = "hard"
        reasons.append("liquidity or utilization hard rule triggered")
    elif rule2Soft or rule4Soft:
        level = "soft"
        reasons.append("liquidity/utilization warning")

    return {
        "level": level,
        "reasons": reasons,
        "metrics": {
            "utilization": utilization,
            "available": available,
            "balance_value": balance_value,
        },
        "conditions": {
            "rule1Hard": rule1Hard,
            "rule2Soft": rule2Soft,
            "rule3Hard": rule3Hard,
            "rule4Soft": rule4Soft,
        },
    }
