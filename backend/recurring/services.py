"""
Recurring rules service — business logic for scheduled transactions.

Port of Go's RecurringService (internal/service/recurring.go) and
RecurringRepo (internal/repository/recurring.go). Combines both layers
into a single service since Django views call the service directly.

Like Laravel's Scheduled Task system — defines rules that fire on a schedule
and create transactions automatically (auto_confirm=true) or after user
confirmation (auto_confirm=false). ProcessDueRules is called on startup,
similar to Laravel's `php artisan schedule:run`.

KEY BEHAVIOR:
- template_transaction is stored as JSONB — parsed when executing the rule.
- When a rule fires, it creates a real transaction via TransactionService.
- After firing, next_due_date advances based on frequency (weekly/monthly).
- Monthly advancement uses dateutil.relativedelta which clamps month overflow
  (Jan 31 + 1 month = Feb 28), unlike Go's time.AddDate which rolls forward
  (Jan 31 + 1 month = Mar 3). The Python behavior is better UX for recurring.
"""

import json
import logging
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from django.db import connection

from transactions.services import TransactionService

logger = logging.getLogger(__name__)

# Columns returned by recurring_rules SELECT queries
_RULE_COLS = [
    "id",
    "user_id",
    "template_transaction",
    "frequency",
    "day_of_month",
    "next_due_date",
    "is_active",
    "auto_confirm",
    "created_at",
    "updated_at",
]


def _row_to_rule(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a recurring_rules SQL row to a dict.

    template_transaction comes back as a Python dict (PostgreSQL JSONB →
    psycopg auto-parses), but may be a string if manually inserted.
    """
    tmpl = row[2]
    if isinstance(tmpl, str):
        tmpl = json.loads(tmpl)

    return {
        "id": str(row[0]),
        "user_id": str(row[1]),
        "template_transaction": tmpl,
        "frequency": row[3],
        "day_of_month": row[4],
        "next_due_date": row[5],
        "is_active": row[6],
        "auto_confirm": row[7],
        "created_at": row[8],
        "updated_at": row[9],
    }


class RecurringService:
    """Manages recurring transaction rules — combined repo + business logic.

    Like Laravel's RecurringRuleService with an injected TransactionService.
    All queries are scoped to self.user_id for multi-user isolation.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_all(self) -> list[dict[str, Any]]:
        """All recurring rules ordered by next_due_date ASC.

        Port of Go's RecurringRepo.GetAll.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, user_id, template_transaction, frequency,
                          day_of_month, next_due_date, is_active, auto_confirm,
                          created_at, updated_at
                   FROM recurring_rules
                   WHERE user_id = %s
                   ORDER BY next_due_date ASC""",
                [self.user_id],
            )
            return [_row_to_rule(row) for row in cursor.fetchall()]

    def get_by_id(self, rule_id: str) -> dict[str, Any] | None:
        """Single rule by ID, scoped to user.

        Port of Go's RecurringRepo.GetByID.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, user_id, template_transaction, frequency,
                          day_of_month, next_due_date, is_active, auto_confirm,
                          created_at, updated_at
                   FROM recurring_rules
                   WHERE id = %s AND user_id = %s""",
                [rule_id, self.user_id],
            )
            row = cursor.fetchone()
            return _row_to_rule(row) if row else None

    def get_due_pending(self) -> list[dict[str, Any]]:
        """Due rules needing user confirmation (auto_confirm=false).

        Port of Go's RecurringService.GetDuePending — fetches all due rules
        then filters to only those requiring manual confirmation.
        """
        today = date.today()
        rules = self._get_due(today)
        return [r for r in rules if not r["auto_confirm"]]

    def _get_due(self, today: date) -> list[dict[str, Any]]:
        """All active rules where next_due_date <= today.

        Port of Go's RecurringRepo.GetDue.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, user_id, template_transaction, frequency,
                          day_of_month, next_due_date, is_active, auto_confirm,
                          created_at, updated_at
                   FROM recurring_rules
                   WHERE is_active = true AND next_due_date <= %s AND user_id = %s
                   ORDER BY next_due_date ASC""",
                [today, self.user_id],
            )
            return [_row_to_rule(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new recurring rule.

        Port of Go's RecurringService.Create — validates required fields,
        inserts JSONB template, returns created rule with generated ID.

        Expects data keys: template_transaction (dict), frequency (str),
        next_due_date (date), auto_confirm (bool).
        """
        tmpl = data.get("template_transaction")
        if not tmpl:
            raise ValueError("template_transaction is required")
        frequency = data.get("frequency", "")
        if not frequency:
            raise ValueError("frequency is required")
        next_due_date = data.get("next_due_date")
        if not next_due_date:
            raise ValueError("next_due_date is required")
        auto_confirm = bool(data.get("auto_confirm", False))

        # Serialize template to JSON string for JSONB column
        tmpl_json = json.dumps(tmpl)

        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO recurring_rules
                   (user_id, template_transaction, frequency, next_due_date,
                    is_active, auto_confirm)
                   VALUES (%s, %s, %s, %s, true, %s)
                   RETURNING id, created_at, updated_at""",
                [self.user_id, tmpl_json, frequency, next_due_date, auto_confirm],
            )
            row = cursor.fetchone()

        assert row is not None
        logger.info("recurring.created frequency=%s user=%s", frequency, self.user_id)
        return {
            "id": str(row[0]),
            "template_transaction": tmpl,
            "frequency": frequency,
            "next_due_date": next_due_date,
            "is_active": True,
            "auto_confirm": auto_confirm,
            "created_at": row[1],
            "updated_at": row[2],
        }

    def confirm(self, rule_id: str) -> None:
        """Execute a pending rule — create transaction + advance due date.

        Port of Go's RecurringService.ConfirmRule.
        """
        rule = self.get_by_id(rule_id)
        if not rule:
            raise ValueError("Rule not found")
        self._execute_rule(rule)
        logger.info("recurring.confirmed id=%s user=%s", rule_id, self.user_id)

    def skip(self, rule_id: str) -> None:
        """Advance next_due_date without creating a transaction.

        Port of Go's RecurringService.SkipRule.
        """
        rule = self.get_by_id(rule_id)
        if not rule:
            raise ValueError("Rule not found")
        next_date = self._advance_due_date(rule)
        self._update_next_due_date(rule_id, next_date)
        logger.info("recurring.skipped id=%s user=%s", rule_id, self.user_id)

    def delete(self, rule_id: str) -> None:
        """Delete a recurring rule.

        Port of Go's RecurringService.Delete.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recurring_rules WHERE id = %s AND user_id = %s",
                [rule_id, self.user_id],
            )
        logger.info("recurring.deleted id=%s user=%s", rule_id, self.user_id)

    def process_due_rules(self) -> int:
        """Auto-process all due rules with auto_confirm=true.

        Port of Go's RecurringService.ProcessDueRules — called on startup.
        Returns count of transactions created.
        """
        today = date.today()
        rules = self._get_due(today)
        created = 0
        for rule in rules:
            if not rule["auto_confirm"]:
                continue
            try:
                self._execute_rule(rule)
                created += 1
                logger.info(
                    "recurring.auto_processed id=%s user=%s",
                    rule["id"],
                    self.user_id,
                )
            except Exception:
                logger.exception(
                    "recurring.auto_process_failed id=%s user=%s",
                    rule["id"],
                    self.user_id,
                )
        return created

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _execute_rule(self, rule: dict[str, Any]) -> None:
        """Create a transaction from the rule template and advance the due date.

        Port of Go's RecurringService.executeRule — the core logic shared by
        confirm() and process_due_rules().

        1. Parse template_transaction (already a dict from JSONB)
        2. Guard: check account_id is not empty
        3. Build transaction data and delegate to TransactionService.create()
        4. Advance next_due_date and persist
        """
        tmpl = rule["template_transaction"]

        account_id = tmpl.get("account_id", "")
        if not account_id:
            raise ValueError(
                f"Recurring rule {rule['id']} has no account_id "
                "— account may have been deleted"
            )

        tx_data: dict[str, Any] = {
            "type": tmpl.get("type", "expense"),
            "amount": tmpl.get("amount", 0),
            "account_id": account_id,
            "date": rule["next_due_date"],
            "recurring_rule_id": rule["id"],
        }
        if tmpl.get("category_id"):
            tx_data["category_id"] = tmpl["category_id"]
        if tmpl.get("note"):
            tx_data["note"] = tmpl["note"]

        # Delegate to TransactionService — handles currency override,
        # atomic balance update, and all validation.
        tx_svc = TransactionService(self.user_id, self.tz)
        tx_svc.create(tx_data)

        next_date = self._advance_due_date(rule)
        self._update_next_due_date(rule["id"], next_date)

    def _advance_due_date(self, rule: dict[str, Any]) -> date:
        """Calculate next due date based on frequency.

        Weekly: +7 days (timedelta).
        Monthly: +1 month (dateutil.relativedelta — clamps month overflow,
        e.g., Jan 31 + 1 month = Feb 28, not Mar 3 like Go's AddDate).
        """
        current: date = rule["next_due_date"]
        freq: str = rule["frequency"]
        if freq == "weekly":
            return current + timedelta(days=7)
        # Default to monthly
        result: date = current + relativedelta(months=1)
        return result

    def _update_next_due_date(self, rule_id: str, next_date: date) -> None:
        """Persist the advanced next_due_date.

        Port of Go's RecurringRepo.UpdateNextDueDate.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE recurring_rules
                   SET next_due_date = %s, updated_at = NOW()
                   WHERE id = %s AND user_id = %s""",
                [next_date, rule_id, self.user_id],
            )

    # ------------------------------------------------------------------
    # View helpers
    # ------------------------------------------------------------------

    def rule_to_view(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Enrich a rule dict with display fields for templates.

        Port of Go's recurringRuleToView — extracts note and amount
        from the JSONB template for display without re-querying.
        """
        tmpl = rule["template_transaction"]
        note = tmpl.get("note") or tmpl.get("type", "")
        amount = tmpl.get("amount", 0)
        currency = tmpl.get("currency", "EGP")
        return {
            **rule,
            "note": note,
            "amount_display": f"{amount:.2f} {currency}",
        }
