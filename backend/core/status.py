from typing import Literal


def compute_threshold_status(
    percentage: float,
    thresholds: tuple[float, float],
) -> Literal["green", "amber", "red"]:
    """Compute status based on percentage vs (warning, critical) threshold pair.

    - green:  percentage < warning_threshold
    - amber:  warning_threshold <= percentage < critical_threshold
    - red:    percentage >= critical_threshold
    """
    warning, critical = thresholds
    if percentage >= critical:
        return "red"
    elif percentage >= warning:
        return "amber"
    return "green"


def compute_spending_velocity_status(
    pct: float,
    day_progress: float,
) -> Literal["green", "amber", "red"]:
    """Compute spending velocity status by comparing spend% vs time progress%.

    - green:  pct <= day_progress
    - amber:  day_progress < pct <= day_progress + 10
    - red:    pct > day_progress + 10
    """
    if pct <= day_progress:
        return "green"
    elif pct <= day_progress + 10:
        return "amber"
    return "red"
