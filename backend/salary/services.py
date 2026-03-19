"""
Salary distribution service — multi-step wizard business logic.

Port of Go's SalaryService (internal/service/salary.go). Creates multiple
transactions atomically: 1 income + 2 exchange + N*2 allocation transfers.

Key design: composes TransactionService methods (create, create_exchange,
create_transfer) inside a single outer transaction.atomic() block. Django's
nested atomic() calls create savepoints, so if any step fails the entire
distribution rolls back.

Like Laravel's SalaryService::distribute() wrapping multiple Model operations
inside DB::transaction(). Django analogy: a service function using
transaction.atomic() to orchestrate multiple TransactionService calls.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from zoneinfo import ZoneInfo

from django.db import transaction

from transactions.services import TransactionService

logger = logging.getLogger(__name__)


@dataclass
class SalaryAllocation:
    """A single allocation target in the salary distribution."""

    account_id: str
    amount: float
    note: str = ""


@dataclass
class SalaryDistribution:
    """Input data for a complete salary distribution."""

    salary_usd: float
    exchange_rate: float
    usd_account_id: str
    egp_account_id: str
    allocations: list[SalaryAllocation] = field(default_factory=list)
    tx_date: date | None = None


@dataclass
class SalaryResult:
    """Summary returned after a successful distribution."""

    salary_usd: float
    exchange_rate: float
    salary_egp: float
    alloc_count: int


class SalaryService:
    """Handles salary distribution — combined validation + orchestration.

    Like Laravel's SalaryService that wraps multiple transaction creations
    in a single DB::transaction(). All queries scoped to self.user_id.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def distribute(self, dist: SalaryDistribution) -> SalaryResult:
        """Distribute salary: income → exchange → allocation transfers.

        Port of Go's SalaryService.DistributeSalary (salary.go:75).
        Creates all transactions atomically using TransactionService composition.

        Raises ValueError for validation failures.
        """
        # --- Validation ---
        if dist.salary_usd <= 0:
            raise ValueError("Salary amount must be positive")
        if dist.exchange_rate <= 0:
            raise ValueError("Exchange rate must be positive")
        if not dist.usd_account_id or not dist.egp_account_id:
            raise ValueError("USD and EGP account IDs are required")

        salary_egp = dist.salary_usd * dist.exchange_rate

        # Filter valid allocations and check total
        valid_allocs = [
            a
            for a in dist.allocations
            if a.amount > 0 and a.account_id != dist.egp_account_id
        ]
        total_alloc = sum(a.amount for a in valid_allocs)
        if total_alloc > salary_egp:
            raise ValueError(
                f"Allocations ({total_alloc:.2f}) exceed salary ({salary_egp:.2f} EGP)"
            )

        tx_date = dist.tx_date or date.today()
        tx_svc = TransactionService(self.user_id, self.tz)

        # --- Atomic distribution ---
        with transaction.atomic():
            # Step 1: Income on USD account
            tx_svc.create(
                {
                    "type": "income",
                    "amount": dist.salary_usd,
                    "account_id": dist.usd_account_id,
                    "note": "Salary",
                    "date": tx_date,
                }
            )

            # Step 2: Exchange USD → EGP
            tx_svc.create_exchange(
                source_id=dist.usd_account_id,
                dest_id=dist.egp_account_id,
                amount=dist.salary_usd,
                rate=dist.exchange_rate,
                counter_amount=None,
                note="Salary exchange",
                tx_date=tx_date,
            )

            # Step 3: Allocation transfers
            for alloc in valid_allocs:
                tx_svc.create_transfer(
                    source_id=dist.egp_account_id,
                    dest_id=alloc.account_id,
                    amount=alloc.amount,
                    currency=None,
                    note=alloc.note or "Salary allocation",
                    tx_date=tx_date,
                )

        logger.info(
            "salary.distributed allocation_count=%d user=%s",
            len(valid_allocs),
            self.user_id,
        )

        return SalaryResult(
            salary_usd=dist.salary_usd,
            exchange_rate=dist.exchange_rate,
            salary_egp=salary_egp,
            alloc_count=len(valid_allocs),
        )
