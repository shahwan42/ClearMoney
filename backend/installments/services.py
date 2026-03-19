"""
Installment service — CRUD + payment recording for installment plans.

Port of Go's InstallmentService (internal/service/installment.go)
and InstallmentRepo (internal/repository/installment.go).

Like Laravel's InstallmentService — validates input, executes raw SQL,
and coordinates with TransactionService for recording payments.

Key design: RecordPayment creates an expense transaction via TransactionService,
then decrements remaining_installments atomically.
"""

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection

from transactions.services import TransactionService

logger = logging.getLogger(__name__)


class InstallmentService:
    """Handles installment plan CRUD and payment recording.

    Like Laravel's InstallmentService wrapping Eloquent queries.
    All queries scoped to self.user_id for multi-user isolation.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_all(self) -> list[dict[str, Any]]:
        """Fetch all installment plans ordered by active first, then newest.

        Port of Go's InstallmentRepo.GetAll (installment.go).
        Returns dicts with computed is_complete and paid_installments fields.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, account_id, description, total_amount,
                       num_installments, monthly_amount, start_date,
                       remaining_installments, created_at, updated_at
                FROM installment_plans
                WHERE user_id = %s
                ORDER BY remaining_installments DESC, start_date DESC
                """,
                [self.user_id],
            )
            rows = cursor.fetchall()

        return [
            {
                "id": str(row[0]),
                "account_id": str(row[1]),
                "description": row[2],
                "total_amount": float(row[3]),
                "num_installments": row[4],
                "monthly_amount": float(row[5]),
                "start_date": row[6],
                "remaining_installments": row[7],
                "created_at": row[8],
                "updated_at": row[9],
                "is_complete": row[7] <= 0,
                "paid_installments": row[4] - row[7],
            }
            for row in rows
        ]

    def get_by_id(self, plan_id: str) -> dict[str, Any]:
        """Fetch a single installment plan by ID.

        Port of Go's InstallmentRepo.GetByID (installment.go).
        Raises ValueError if not found.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, account_id, description, total_amount,
                       num_installments, monthly_amount, start_date,
                       remaining_installments, created_at, updated_at
                FROM installment_plans
                WHERE id = %s AND user_id = %s
                """,
                [plan_id, self.user_id],
            )
            row = cursor.fetchone()

        if not row:
            raise ValueError("Installment plan not found")

        return {
            "id": str(row[0]),
            "account_id": str(row[1]),
            "description": row[2],
            "total_amount": float(row[3]),
            "num_installments": row[4],
            "monthly_amount": float(row[5]),
            "start_date": row[6],
            "remaining_installments": row[7],
            "created_at": row[8],
            "updated_at": row[9],
            "is_complete": row[7] <= 0,
            "paid_installments": row[4] - row[7],
        }

    def create(self, data: dict[str, Any]) -> str:
        """Create a new installment plan.

        Port of Go's InstallmentService.Create (installment.go).
        Validates inputs, auto-computes monthly_amount, inserts, and logs.

        Raises ValueError for validation failures.
        Returns the new plan ID.
        """
        description = (data.get("description") or "").strip()
        if not description:
            raise ValueError("Description is required")

        total_amount = float(data.get("total_amount", 0))
        if total_amount <= 0:
            raise ValueError("Total amount must be positive")

        num_installments = int(data.get("num_installments", 0))
        if num_installments <= 0:
            raise ValueError("Number of installments must be positive")

        account_id = (data.get("account_id") or "").strip()
        if not account_id:
            raise ValueError("Account is required")

        # Auto-compute monthly amount
        monthly_amount = total_amount / num_installments

        # Parse start_date
        start_date = data.get("start_date")
        if isinstance(start_date, str) and start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        elif not isinstance(start_date, date):
            start_date = datetime.now(self.tz).date()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO installment_plans
                    (user_id, account_id, description, total_amount,
                     num_installments, monthly_amount, start_date,
                     remaining_installments)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [
                    self.user_id,
                    account_id,
                    description,
                    total_amount,
                    num_installments,
                    monthly_amount,
                    start_date,
                    num_installments,  # remaining = total on creation
                ],
            )
            row = cursor.fetchone()
            assert row is not None
            new_id = str(row[0])

        logger.info(
            "installment.created id=%s account_id=%s user=%s",
            new_id,
            account_id,
            self.user_id,
        )
        return new_id

    def record_payment(self, plan_id: str) -> None:
        """Record a payment on an installment plan.

        Port of Go's InstallmentService.RecordPayment (installment.go).
        Two-step: creates expense transaction via TransactionService, then
        decrements remaining_installments atomically.

        Raises ValueError if plan is fully paid or not found.
        """
        plan = self.get_by_id(plan_id)

        if plan["remaining_installments"] <= 0:
            raise ValueError("Plan already fully paid")

        # Create expense transaction for the monthly amount
        paid = plan["paid_installments"] + 1
        note = f"Installment {paid}/{plan['num_installments']}: {plan['description']}"

        tx_svc = TransactionService(self.user_id, self.tz)
        tx_svc.create(
            {
                "type": "expense",
                "amount": plan["monthly_amount"],
                "account_id": plan["account_id"],
                "note": note,
            }
        )

        # Decrement remaining (atomic guard prevents going negative)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE installment_plans
                SET remaining_installments = remaining_installments - 1,
                    updated_at = NOW()
                WHERE id = %s AND remaining_installments > 0 AND user_id = %s
                """,
                [plan_id, self.user_id],
            )

        logger.info(
            "installment.payment_recorded id=%s user=%s",
            plan_id,
            self.user_id,
        )

    def delete(self, plan_id: str) -> None:
        """Delete an installment plan.

        Port of Go's InstallmentService.Delete (installment.go).
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM installment_plans WHERE id = %s AND user_id = %s",
                [plan_id, self.user_id],
            )

        logger.info(
            "installment.deleted id=%s user=%s",
            plan_id,
            self.user_id,
        )
