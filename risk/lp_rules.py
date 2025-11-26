from typing import Dict, List


def evaluate(metrics: Dict[str, float]) -> Dict[str, object]:
    """
    Placeholder LP risk model. Extend with TVL/depth/volume/IL metrics when available.
    """
    reasons: List[str] = []
    level = "ok"
    return {
        "level": level,
        "reasons": reasons,
        "metrics": metrics,
    }
