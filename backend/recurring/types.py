"""
Recurring rule-related types for cross-module use.

Exports: RecurringRulePending
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class RecurringRulePending:
    """Recurring rule awaiting user confirmation.

    Returned by RecurringService.get_due_pending() and used by:
    - recurring/views.py (displaying pending rules)
    - push/services.py (recurring transaction due notifications)
    """

    id: str
    user_id: str
    frequency: str  # "weekly" | "monthly"
    day_of_month: int | None
    next_due_date: date
    is_active: bool
    auto_confirm: bool
    template_transaction: dict[str, Any]  # JSONB: note, amount, account_id, etc.
    created_at: datetime | None
    updated_at: datetime | None
