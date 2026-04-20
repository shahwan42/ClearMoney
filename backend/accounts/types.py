"""
Account-related types for cross-module use.

HealthWarning is exported to push/services.py and re-exported through
dashboard/services for backward compatibility.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HealthWarning:
    """Account health warning condition.

    Fired when an account violates a configured health constraint
    (min_balance, min_monthly_deposit).
    """

    account_name: str  # e.g., "Savings Account", "Current"
    account_id: str  # UUID of the account
    rule: str  # "min_balance" | "min_monthly_deposit"
    message: str  # Human-readable warning message


@dataclass(frozen=True)
class AccountSummary:
    """Full account data — used by same-module views and cross-module consumers.

    Returned by AccountService.get_all() and used by:
    - accounts/views.py (JSON API)
    - push/services.py (notifications)
    """

    id: str
    name: str
    institution_id: str | None
    currency: str
    type: str  # savings | current | prepaid | cash | credit_card | credit_limit
    current_balance: float
    initial_balance: float
    credit_limit: float | None
    is_dormant: bool
    is_credit_type: bool
    available_credit: float | None
    role_tags: list
    display_order: int
    metadata: dict | None
    health_config: dict | None
    last_reconciled_at: datetime | str | None = None
    last_balance_check_at: datetime | str | None = None
    last_checked_balance: float | None = None
    last_balance_check_diff: float | None = None
    last_balance_check_status: str | None = None
    created_at: object | None = None  # datetime
    updated_at: object | None = None  # datetime


@dataclass
class NetWorthSummary:
    """Net worth breakdown from account balances.

    Used by dashboard and any module that needs net worth computation.
    """

    net_worth: float = 0.0
    egp_total: float = 0.0
    usd_total: float = 0.0
    cash_total: float = 0.0  # EGP liquid cash (non-credit, positive balance)
    cash_usd: float = 0.0  # USD liquid cash (non-credit, positive balance)
    credit_used: float = 0.0
    credit_avail: float = 0.0
    debt_total: float = 0.0
    debt_egp: float = 0.0
    debt_usd: float = 0.0


@dataclass(frozen=True)
class AccountDropdownItem:
    """Lightweight account for form dropdowns.

    Returned by AccountService.get_for_dropdown() and used by:
    - people/views.py
    - virtual_accounts/views.py
    - recurring/views.py
    """

    id: str
    name: str
    currency: str
    current_balance: float | None = None  # present only when include_balance=True
