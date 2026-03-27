"""
Recurring rules service — business logic for scheduled transactions.

Like Laravel's Scheduled Task system — defines rules that fire on a schedule
and create transactions automatically (auto_confirm=true) or after user
confirmation (auto_confirm=false). ProcessDueRules is called on startup,
similar to Laravel's `php artisan schedule:run`.

KEY BEHAVIOR:
- template_transaction is stored as JSONB — Django's JSONField auto-parses it.
- When a rule fires, it creates a real transaction via TransactionService.
- After firing, next_due_date advances based on frequency (weekly/monthly).
- Monthly advancement uses dateutil.relativedelta which clamps month overflow
  (e.g., Jan 31 + 1 month = Feb 28). This is better UX than rolling forward to Mar 3.
"""

import json
import logging
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from django.utils import timezone as django_tz

from recurring.models import RecurringRule
from recurring.types import RecurringRulePending
from transactions.services import TransactionService

logger = logging.getLogger(__name__)

# Fields returned by .values() queries — matches the old _RULE_COLS
_FIELDS = (
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
)


def _row_to_rule(row: dict[str, Any]) -> RecurringRulePending:
    """Convert a .values() dict to a RecurringRulePending.

    template_transaction comes back as a Python dict from Django's JSONField,
    but may be a string if manually inserted.
    """
    tmpl = row["template_transaction"]
    if isinstance(tmpl, str):
        tmpl = json.loads(tmpl)

    return RecurringRulePending(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        template_transaction=tmpl,
        frequency=row["frequency"],
        day_of_month=row["day_of_month"],
        next_due_date=row["next_due_date"],
        is_active=row["is_active"],
        auto_confirm=row["auto_confirm"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _instance_to_rule(inst: RecurringRule) -> RecurringRulePending:
    """Convert a RecurringRule model instance to a RecurringRulePending dataclass."""
    tmpl = inst.template_transaction
    if isinstance(tmpl, str):
        tmpl = json.loads(tmpl)

    return RecurringRulePending(
        id=str(inst.id),
        user_id=str(inst.user_id),
        template_transaction=tmpl,
        frequency=inst.frequency,
        day_of_month=inst.day_of_month,
        next_due_date=inst.next_due_date,
        is_active=inst.is_active,
        auto_confirm=inst.auto_confirm,
        created_at=inst.created_at,
        updated_at=inst.updated_at,
    )


class RecurringService:
    """Manages recurring transaction rules — combined repo + business logic.

    Like Laravel's RecurringRuleService with an injected TransactionService.
    All queries are scoped to self.user_id for multi-user isolation.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return RecurringRule.objects.for_user(self.user_id)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_all(self) -> list[RecurringRulePending]:
        """All recurring rules ordered by next_due_date ASC."""
        rows = self._qs().order_by("next_due_date").values(*_FIELDS)
        return [_row_to_rule(row) for row in rows]

    def get_by_id(self, rule_id: str) -> RecurringRulePending | None:
        """Single rule by ID, scoped to user."""
        row = self._qs().filter(id=rule_id).values(*_FIELDS).first()
        if not row:
            return None
        return _row_to_rule(row)

    def get_due_pending(self) -> list[RecurringRulePending]:
        """Due rules needing user confirmation (auto_confirm=false).

        Fetches all due rules then filters to those requiring manual confirmation.
        """
        today = date.today()
        rules = self._get_due(today)
        return [r for r in rules if not r.auto_confirm]

    def _get_due(self, today: date) -> list[RecurringRulePending]:
        """All active rules where next_due_date <= today."""
        rows = (
            self._qs()
            .filter(is_active=True, next_due_date__lte=today)
            .order_by("next_due_date")
            .values(*_FIELDS)
        )
        return [_row_to_rule(row) for row in rows]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> RecurringRulePending:
        """Create a new recurring rule.

        Validates required fields, inserts JSONB template, returns created rule.
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

        rule = RecurringRule.objects.create(
            user_id=self.user_id,
            template_transaction=tmpl,
            frequency=frequency,
            next_due_date=next_due_date,
            is_active=True,
            auto_confirm=auto_confirm,
        )

        logger.info("recurring.created frequency=%s user=%s", frequency, self.user_id)
        return _instance_to_rule(rule)

    def confirm(self, rule_id: str) -> None:
        """Execute a pending rule — create transaction + advance due date."""
        rule = self.get_by_id(rule_id)
        if not rule:
            raise ValueError("Rule not found")
        self._execute_rule(rule)
        logger.info("recurring.confirmed id=%s user=%s", rule_id, self.user_id)

    def skip(self, rule_id: str) -> None:
        """Advance next_due_date without creating a transaction."""
        rule = self.get_by_id(rule_id)
        if not rule:
            raise ValueError("Rule not found")
        next_date = self._advance_due_date(rule)
        self._update_next_due_date(rule_id, next_date)
        logger.info("recurring.skipped id=%s user=%s", rule_id, self.user_id)

    def delete(self, rule_id: str) -> None:
        """Delete a recurring rule."""
        self._qs().filter(id=rule_id).delete()
        logger.info("recurring.deleted id=%s user=%s", rule_id, self.user_id)

    def process_due_rules(self) -> int:
        """Auto-process all due rules with auto_confirm=true.

        Called on startup. Returns count of transactions created.
        """
        today = date.today()
        rules = self._get_due(today)
        created = 0
        for rule in rules:
            if not rule.auto_confirm:
                continue
            try:
                self._execute_rule(rule)
                created += 1
                logger.info(
                    "recurring.auto_processed id=%s user=%s",
                    rule.id,
                    self.user_id,
                )
            except Exception:
                logger.exception(
                    "recurring.auto_process_failed id=%s user=%s",
                    rule.id,
                    self.user_id,
                )
        return created

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _execute_rule(self, rule: RecurringRulePending) -> None:
        """Create a transaction from the rule template and advance the due date.

        Core logic shared by confirm() and process_due_rules().

        1. Parse template_transaction (already a dict from JSONB)
        2. Guard: check account_id is not empty
        3. Build transaction data and delegate to TransactionService.create()
        4. Advance next_due_date and persist
        """
        tmpl = rule.template_transaction

        account_id = tmpl.get("account_id", "")
        if not account_id:
            raise ValueError(
                f"Recurring rule {rule.id} has no account_id "
                "— account may have been deleted"
            )

        tx_data: dict[str, Any] = {
            "type": tmpl.get("type", "expense"),
            "amount": tmpl.get("amount", 0),
            "account_id": account_id,
            "date": rule.next_due_date,
            "recurring_rule_id": rule.id,
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
        self._update_next_due_date(rule.id, next_date)

    def _advance_due_date(self, rule: RecurringRulePending) -> date:
        """Calculate next due date based on frequency.

        Weekly: +7 days (timedelta).
        Monthly: +1 month (dateutil.relativedelta — clamps month overflow,
        e.g., Jan 31 + 1 month = Feb 28).
        """
        current: date = rule.next_due_date
        freq: str = rule.frequency
        if freq == "weekly":
            return current + timedelta(days=7)
        # Default to monthly
        result: date = current + relativedelta(months=1)
        return result

    def _update_next_due_date(self, rule_id: str, next_date: date) -> None:
        """Persist the advanced next_due_date."""
        self._qs().filter(id=rule_id).update(
            next_due_date=next_date, updated_at=django_tz.now()
        )

    # ------------------------------------------------------------------
    # View helpers
    # ------------------------------------------------------------------

    def rule_to_view(
        self, rule: RecurringRulePending | dict[str, Any]
    ) -> dict[str, Any]:
        """Enrich a rule with display fields for templates.

        Extracts note and amount from the JSONB template for display without re-querying.
        Accepts both RecurringRulePending dataclass and dict for backward compatibility.
        """
        # Handle both dataclass and dict access patterns
        if isinstance(rule, dict):
            tmpl = rule.get("template_transaction", {})
            rule_id = rule.get("id")
            user_id = rule.get("user_id")
            frequency = rule.get("frequency")
            day_of_month = rule.get("day_of_month")
            next_due_date = rule.get("next_due_date")
            is_active = rule.get("is_active")
            auto_confirm = rule.get("auto_confirm")
            created_at = rule.get("created_at")
            updated_at = rule.get("updated_at")
            template_transaction = tmpl
        else:
            tmpl = rule.template_transaction
            rule_id = rule.id
            user_id = rule.user_id
            frequency = rule.frequency
            day_of_month = rule.day_of_month
            next_due_date = rule.next_due_date
            is_active = rule.is_active
            auto_confirm = rule.auto_confirm
            created_at = rule.created_at
            updated_at = rule.updated_at
            template_transaction = rule.template_transaction

        note = tmpl.get("note") or tmpl.get("type", "")
        amount = tmpl.get("amount", 0)
        currency = tmpl.get("currency", "EGP")
        return {
            "id": rule_id,
            "user_id": user_id,
            "template_transaction": template_transaction,
            "frequency": frequency,
            "day_of_month": day_of_month,
            "next_due_date": next_due_date,
            "is_active": is_active,
            "auto_confirm": auto_confirm,
            "created_at": created_at,
            "updated_at": updated_at,
            "note": note,
            "amount_display": f"{amount:.2f} {currency}",
        }
