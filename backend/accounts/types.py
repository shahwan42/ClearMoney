"""
Account-related types for cross-module use.

HealthWarning is exported to push/services.py and re-exported through
dashboard/services for backward compatibility.
"""

from dataclasses import dataclass


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
