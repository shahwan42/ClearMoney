"""
Core models — Django representations of the ClearMoney PostgreSQL schema.

All models map to existing tables. Django manages migrations natively.

Like Laravel's Eloquent models with $table, or Django's standard models
with explicit db_table to match the existing schema naming convention.

Phase 3 migration complete: all models have been moved to their respective
app-specific models.py files. This file contains re-export shims for backward
compatibility during the gradual import site migration (Phase 3 Cleanup).
All 47 import sites should eventually be updated to import directly from
their owning apps, after which these shims can be removed.

Note: import-linter will report violations until cleanup is complete.
"""

# Re-export shims — models moved to their own apps (Phase 3 migration).
from accounts.models import Account as Account  # noqa: F401
from accounts.models import Institution as Institution  # noqa: F401
from auth_app.models import AuthToken as AuthToken  # noqa: F401
from auth_app.models import Session as Session  # noqa: F401
from auth_app.models import User as User  # noqa: F401
from auth_app.models import UserConfig as UserConfig  # noqa: F401
from budgets.models import Budget as Budget  # noqa: F401
from budgets.models import TotalBudget as TotalBudget  # noqa: F401
from categories.models import Category as Category  # noqa: F401
from exchange_rates.models import ExchangeRateLog as ExchangeRateLog  # noqa: F401
from investments.models import Investment as Investment  # noqa: F401
from jobs.models import AccountSnapshot as AccountSnapshot  # noqa: F401
from jobs.models import DailySnapshot as DailySnapshot  # noqa: F401
from people.models import Person as Person  # noqa: F401
from recurring.models import RecurringRule as RecurringRule  # noqa: F401
from transactions.models import Transaction as Transaction  # noqa: F401
from transactions.models import (  # noqa: F401
    VirtualAccountAllocation as VirtualAccountAllocation,
)
from virtual_accounts.models import VirtualAccount as VirtualAccount  # noqa: F401
