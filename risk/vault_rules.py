from typing import Dict, List


def evaluate(metrics: Dict[str, float]) -> Dict[str, object]:
    """
    Vault / structured product risk model.

    Inputs:
      metrics.idle_ratio: idle NAV / total NAV
      metrics.deployment_rate: 1 - idle_ratio
      metrics.nav_delta: optional, NAV change % (not used yet)
      metrics.api_lag_seconds: optional, adapter staleness (not used yet)

    Returns:
      {"level": "hard"|"soft"|"ok", "reasons": [...], "metrics": {...}}
    """
    idle_ratio = float(metrics.get("idle_ratio", 0.0) or 0.0)
    deployment_rate = float(metrics.get("deployment_rate", 0.0) or 0.0)

    reasons: List[str] = []
    level = "ok"

    if idle_ratio < 0.05 or deployment_rate > 0.95:
        reasons.append(f"idle_ratio only {idle_ratio:.2%} / deployment_rate {deployment_rate:.2%}")
        level = "hard"
    elif idle_ratio < 0.2 or deployment_rate > 0.8:
        reasons.append(f"idle_ratio low {idle_ratio:.2%} / deployment_rate {deployment_rate:.2%}")
        level = "soft"

    return {
        "level": level,
        "reasons": reasons,
        "metrics": {
            "idle_ratio": idle_ratio,
            "deployment_rate": deployment_rate,
        },
    }
