"""
Budget-related types for cross-module use.

Exports: BudgetWithSpending
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetWithSpending:
    """Budget with current month's spending summary.

    Returned by BudgetService.get_all_with_spending() and used by:
    - budgets/views.py (UI rendering)
    - push/services.py (budget threshold notifications)
    """

    id: str
    category_id: str
    category_name: str
    category_icon: str
    monthly_limit: float
    currency: str
    spent: float
    remaining: float
    percentage: float  # spent / limit * 100
    status: str  # "green" | "amber" | "red"
