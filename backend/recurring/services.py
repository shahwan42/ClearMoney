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

from core.serializers import serialize_value
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


def _parse_template(val: Any) -> Any:
    """Parse template_transaction JSON if stored as a string."""
    if isinstance(val, str):
        return json.loads(val)
    return val


def _row_to_rule(row: dict[str, Any]) -> RecurringRulePending:
    """Convert a .values() dict to a RecurringRulePending."""
    d: dict[str, Any] = {
        f: serialize_value(row[f]) for f in _FIELDS if f != "template_transaction"
    }
    d["template_transaction"] = _parse_template(row["template_transaction"])
    return RecurringRulePending(**d)


def _instance_to_rule(inst: RecurringRule) -> RecurringRulePending:
    """Convert a RecurringRule model instance to a RecurringRulePending dataclass."""
    d: dict[str, Any] = {
        f: serialize_value(getattr(inst, f))
        for f in _FIELDS
        if f != "template_transaction"
    }
    d["template_transaction"] = _parse_template(inst.template_transaction)
    return RecurringRulePending(**d)


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
        3. Route to create_transfer() for transfers, or create() for expense/income
        4. Advance next_due_date and persist
        """
        tmpl = rule.template_transaction

        account_id = tmpl.get("account_id", "")
        if not account_id:
            raise ValueError(
                f"Recurring rule {rule.id} has no account_id "
                "— account may have been deleted"
            )

        tx_svc = TransactionService(self.user_id, self.tz)

        if tmpl.get("type") == "transfer":
            counter_account_id = tmpl.get("counter_account_id", "")
            if not counter_account_id:
                raise ValueError(
                    f"Recurring rule {rule.id} has no counter_account_id "
                    "— destination account may have been deleted"
                )
            tx_svc.create_transfer(
                source_id=account_id,
                dest_id=counter_account_id,
                amount=tmpl.get("amount", 0),
                currency=None,
                note=tmpl.get("note"),
                tx_date=rule.next_due_date,
                fee_amount=tmpl.get("fee_amount"),
            )
        else:
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

    def _format_template_display(self, template: dict[str, Any]) -> dict[str, Any]:
        """Extract and format template fields for display in views.

        Transforms template_transaction (JSONB dict) into display-ready fields:
        - note: rule note or fallback to transaction type
        - amount_display: formatted as "X.XX CURRENCY"
        - is_transfer: True if type == "transfer"
        - fee_display: for transfers with fees, formatted as "X.XX CURRENCY"

        Args:
            template: template_transaction dict from RecurringRule JSONB

        Returns:
            dict with keys: note, amount_display, is_transfer, fee_display (optional)
        """
        note = template.get("note") or template.get("type", "")
        amount = template.get("amount", 0)
        currency = template.get("currency", "EGP")
        is_transfer = template.get("type") == "transfer"

        result: dict[str, Any] = {
            "note": note,
            "amount_display": f"{amount:.2f} {currency}",
            "is_transfer": is_transfer,
        }

        if is_transfer:
            fee = template.get("fee_amount")
            if fee and float(fee) > 0:
                result["fee_display"] = f"{float(fee):.2f} {currency}"

        return result

    def _get_account_names(
        self, account_id: str, counter_account_id: str
    ) -> dict[str, str]:
        """Look up account names for a transfer rule.

        Fetches both source and destination account names from the database.
        Used only for transfer rules (type="transfer").

        Args:
            account_id: source account UUID
            counter_account_id: destination account UUID

        Returns:
            dict with keys: source_account_name, counter_account_name
            Falls back to "Unknown" if account is not found or deleted.
        """
        from accounts.models import Account

        source_name = (
            Account.objects.filter(id=account_id).values_list("name", flat=True).first()
            or "Unknown"
        )
        counter_name = (
            Account.objects.filter(id=counter_account_id)
            .values_list("name", flat=True)
            .first()
            or "Unknown"
        )

        return {
            "source_account_name": source_name,
            "counter_account_name": counter_name,
        }

    def rule_to_view(self, rule: RecurringRulePending) -> dict[str, Any]:
        """Enrich a rule with display fields for templates.

        Combines rule metadata with template display formatting:
        - Core fields: id, user_id, frequency, next_due_date, etc.
        - Template display fields: note, amount_display, is_transfer
        - Transfer-specific fields: source_account_name, counter_account_name, fee_display

        Extracts note and amount from JSONB template without re-querying.
        For transfers, performs additional DB lookup to fetch account names
        (accounts may have been deleted; returns "Unknown" as fallback).

        Args:
            rule: RecurringRulePending dataclass with JSONB template_transaction

        Returns:
            dict suitable for template rendering, with all rule + display fields
        """
        tmpl = rule.template_transaction

        # Format template-specific display fields
        template_display = self._format_template_display(tmpl)

        # Build base view dict with all rule fields
        result: dict[str, Any] = {
            "id": rule.id,
            "user_id": rule.user_id,
            "template_transaction": rule.template_transaction,
            "frequency": rule.frequency,
            "day_of_month": rule.day_of_month,
            "next_due_date": rule.next_due_date,
            "is_active": rule.is_active,
            "auto_confirm": rule.auto_confirm,
            "created_at": rule.created_at,
            "updated_at": rule.updated_at,
        }

        # Merge template display fields
        result.update(template_display)

        # For transfers, look up and add account names
        if template_display["is_transfer"]:
            account_names = self._get_account_names(
                tmpl.get("account_id", ""),
                tmpl.get("counter_account_id", ""),
            )
            result.update(account_names)

        return result
