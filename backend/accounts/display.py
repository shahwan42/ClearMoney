"""
Display helpers for account-related UI computations.

This module provides functions to compute display-layer values (colors, capped
percentages) that should live in the service/view layer instead of templates.
All logic is testable, documented, and separated from template rendering.
"""

from decimal import Decimal


def get_balance_color_class(balance: Decimal | float) -> str:
    """
    Return Tailwind color classes for account balance display.

    Args:
        balance: Account current_balance as Decimal or float

    Returns:
        Tailwind CSS class string for conditional balance coloring:
        - "text-red-600" if balance < 0 (debt/overdraft)
        - "text-teal-700 dark:text-teal-400" if balance >= 0 (positive)
    """
    if balance < 0:
        return "text-red-600"
    return "text-teal-700 dark:text-teal-400"


def get_your_money_color_class(balance: Decimal | float) -> str:
    """
    Return Tailwind color classes for 'your money' balance (after VA exclusion).

    Args:
        balance: Decimal or float (account.current_balance - excluded_va_balance)

    Returns:
        Tailwind CSS class string:
        - "text-red-600" if balance < 0
        - "text-teal-600" if balance >= 0
    """
    if balance < 0:
        return "text-red-600"
    return "text-teal-600"


def get_utilization_color_hex(utilization_pct: float) -> str:
    """
    Return hex color for credit utilization indicator circle.

    Thresholds:
        > 80%: red (danger)
        > 50%: amber (warning)
        <= 50%: green (healthy)

    Args:
        utilization_pct: Credit utilization percentage (0-200+)

    Returns:
        Hex color string for SVG stroke:
        - "#ef4444" (red) if > 80%
        - "#f59e0b" (amber) if > 50%
        - "#10b981" (green) otherwise
    """
    if utilization_pct > 80:
        return "#ef4444"  # red-600
    if utilization_pct > 50:
        return "#f59e0b"  # amber-400
    return "#10b981"  # emerald-600
