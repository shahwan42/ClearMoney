"""Transaction service package — business logic for transactions, transfers, exchanges.

Composes TransactionService from a base class and mixins:
- TransactionServiceBase: __init__, private helpers, CRUD operations
- TransferMixin: transfers, InstaPay, exchange
- HelperMixin: batch create, smart defaults, VA allocation, dropdowns

CRITICAL INVARIANTS:
- Currency is ALWAYS overridden from the account record (never trust form input).
- All balance updates are atomic (wrapped in transaction.atomic()).
- Exchange rates are always stored as "EGP per 1 USD".
- Amount is always positive; BalanceDelta holds the signed impact.
"""

from .activity import StreakInfo, TransactionRow, load_recent_transactions, load_streak
from .crud import TransactionServiceBase
from .csv_import import CsvImportService
from .helpers import HelperMixin
from .tags import TagService
from .transfers import TransferMixin
from .utils import (
    CREDIT_ACCOUNT_TYPES,
    VALID_TX_TYPES,
    resolve_exchange_fields,
)


class TransactionService(TransferMixin, HelperMixin, TransactionServiceBase):
    """Full transaction service — composed from base class + mixins.

    Like Laravel's TransactionService — validates input, executes atomic SQL,
    logs mutations. Takes user_id and tz in __init__ (same as AccountService).
    """

    pass


__all__ = [
    "TransactionService",
    "TransactionServiceBase",
    "TransferMixin",
    "HelperMixin",
    "TagService",
    "VALID_TX_TYPES",
    "CREDIT_ACCOUNT_TYPES",
    "resolve_exchange_fields",
    "CsvImportService",
    # Activity (extracted from dashboard)
    "TransactionRow",
    "StreakInfo",
    "load_recent_transactions",
    "load_streak",
]
