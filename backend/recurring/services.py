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
        if auto_confirm and tmpl.get("type") == "exchange":
            raise ValueError(
                "Exchange rules cannot use auto_confirm — rate must be confirmed manually"
            )

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

    def update(self, rule_id: str, data: dict[str, Any]) -> RecurringRulePending:
        """Update an existing recurring rule.

        Supports partial updates — only provided keys are changed.
        Raises ValueError if rule not found or validation fails.
        """
        rule = self._qs().filter(id=rule_id).first()
        if not rule:
            raise ValueError(f"Recurring rule not found: {rule_id}")

        if "template_transaction" in data:
            rule.template_transaction = data["template_transaction"]
        if "frequency" in data:
            rule.frequency = data["frequency"]
        if "next_due_date" in data:
            rule.next_due_date = data["next_due_date"]
        if "auto_confirm" in data:
            auto_confirm = bool(data["auto_confirm"])
            if auto_confirm and rule.template_transaction.get("type") == "exchange":
                raise ValueError(
                    "Exchange rules cannot use auto_confirm — rate must be confirmed manually"
                )
            rule.auto_confirm = auto_confirm

        rule.save(
            update_fields=[
                "template_transaction",
                "frequency",
                "next_due_date",
                "auto_confirm",
                "updated_at",
            ]
        )
        logger.info("recurring.updated id=%s user=%s", rule_id, self.user_id)
        return _instance_to_rule(rule)

    def confirm(self, rule_id: str, overrides: dict[str, Any] | None = None) -> None:
        """Execute a pending rule — create transaction + advance due date.

        If overrides are provided, they take precedence over the template transaction.
        Supported overrides: amount, account_id, category_id, note, date,
        counter_account_id, exchange_rate, tags, va_id, fee_amount.
        """
        rule = self.get_by_id(rule_id)
        if not rule:
            raise ValueError("Rule not found")
        self._execute_rule(rule, overrides=overrides)

        actual_amount = overrides.get("amount") if overrides else None
        if actual_amount is not None:
            expected = float(rule.template_transaction.get("amount", 0))
            if expected != actual_amount:
                logger.info(
                    "recurring.confirmed id=%s user=%s expected=%.2f actual=%.2f deviation=%.2f%%",
                    rule_id,
                    self.user_id,
                    expected,
                    actual_amount,
                    ((actual_amount - expected) / expected * 100) if expected else 0,
                )
            else:
                logger.info("recurring.confirmed id=%s user=%s", rule_id, self.user_id)
        else:
            logger.info("recurring.confirmed id=%s user=%s", rule_id, self.user_id)

    def confirm_all(self, year: int | None = None, month: int | None = None) -> int:
        """Confirm all due rules for a specific month (default: today).

        Returns count of transactions created.
        """
        if year and month:
            # Last day of month
            import calendar

            _, last_day = calendar.monthrange(year, month)
            due_by = date(year, month, last_day)
        else:
            due_by = date.today()

        rules = self._get_due(due_by)
        confirmed = 0
        for rule in rules:
            try:
                self.confirm(rule.id)
                confirmed += 1
            except Exception:
                logger.exception(
                    "recurring.confirm_all_failed id=%s user=%s", rule.id, self.user_id
                )
        return confirmed

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

    def build_template_transaction(self, data: dict[str, Any]) -> dict[str, Any]:
        """Build template_transaction JSONB from raw form data.

        Handles amount parsing, currency lookup, and transfer-specific logic.
        """
        tx_type = data.get("type", "expense")
        account_id = data.get("account_id", "")
        if not account_id:
            raise ValueError("account_id is required")

        # Parse amount
        try:
            amount = float(data.get("amount", 0))
        except (ValueError, TypeError):
            raise ValueError("Amount is required")

        # Look up account currency (server-side override, never trust form)
        from accounts.models import Account

        currency = (
            Account.objects.for_user(self.user_id)
            .filter(id=account_id)
            .values_list("currency", flat=True)
            .first()
            or "EGP"
        )

        if tx_type in ("transfer", "exchange"):
            counter_account_id = data.get("counter_account_id", "")
            if not counter_account_id:
                raise ValueError(
                    "Destination account is required for transfers/exchanges"
                )
            if counter_account_id == account_id:
                raise ValueError("Source and destination accounts must be different")

            # Auto-detect exchange when currencies differ (like Quick Entry)
            dest_currency = (
                Account.objects.for_user(self.user_id)
                .filter(id=counter_account_id)
                .values_list("currency", flat=True)
                .first()
                or currency
            )
            if tx_type == "transfer" and dest_currency != currency:
                tx_type = "exchange"

            template: dict[str, Any] = {
                "type": tx_type,
                "amount": amount,
                "currency": currency,
                "account_id": account_id,
                "counter_account_id": counter_account_id,
            }

            # Parse optional fee (transfers only)
            fee_str = data.get("fee_amount", "")
            if fee_str:
                try:
                    fee_val = float(fee_str)
                    if fee_val > 0:
                        template["fee_amount"] = fee_val
                except (ValueError, TypeError):
                    pass

            # Exchange rate — optional at rule creation
            if tx_type == "exchange":
                rate_str = data.get("exchange_rate", "")
                if rate_str:
                    try:
                        rate_val = float(rate_str)
                        if rate_val > 0:
                            template["exchange_rate"] = rate_val
                    except (ValueError, TypeError):
                        pass
        else:
            template = {
                "type": tx_type,
                "amount": amount,
                "currency": currency,
                "account_id": account_id,
            }
            category_id = data.get("category_id")
            if category_id:
                template["category_id"] = category_id

            # Optional fields for expense/income
            tags = data.get("tags", "")
            if tags:
                template["tags"] = tags
            va_id = data.get("va_id", "")
            if va_id:
                template["va_id"] = va_id
            fee_str = data.get("fee_amount", "")
            if fee_str:
                try:
                    fee_val = float(fee_str)
                    if fee_val > 0:
                        template["fee_amount"] = fee_val
                except (ValueError, TypeError):
                    pass

        note = data.get("note")
        if note:
            template["note"] = note

        return template

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

    def _execute_rule(
        self, rule: RecurringRulePending, overrides: dict[str, Any] | None = None
    ) -> None:
        """Create a transaction from the rule template and advance the due date.

        Core logic shared by confirm() and process_due_rules().

        1. Parse template_transaction (already a dict from JSONB)
        2. Guard: check account_id is not empty
        3. Route to create_transfer() for transfers, or create() for expense/income
        4. Advance next_due_date and persist

        overrides: if provided, takes precedence over the template fields.
        """
        tmpl = rule.template_transaction
        overrides = overrides or {}

        # Fields with overrides
        account_id = overrides.get("account_id") or tmpl.get("account_id", "")
        amount = (
            overrides.get("amount")
            if overrides.get("amount") is not None
            else tmpl.get("amount", 0)
        )
        tx_date = overrides.get("date") or rule.next_due_date
        note = (
            overrides.get("note")
            if overrides.get("note") is not None
            else tmpl.get("note")
        )

        if not account_id:
            raise ValueError(
                f"Recurring rule {rule.id} has no account_id "
                "— account may have been deleted"
            )

        tx_svc = TransactionService(self.user_id, self.tz)

        tx_type = tmpl.get("type", "expense")

        if tx_type in ("transfer", "exchange"):
            counter_account_id = overrides.get("counter_account_id") or tmpl.get(
                "counter_account_id", ""
            )
            if not counter_account_id:
                raise ValueError(
                    f"Recurring rule {rule.id} has no counter_account_id "
                    "— destination account may have been deleted"
                )

            if tx_type == "exchange":
                exchange_rate = overrides.get("exchange_rate") or tmpl.get(
                    "exchange_rate"
                )
                if not exchange_rate:
                    raise ValueError(
                        "Exchange rate is required to confirm an exchange rule"
                    )
                tx_svc.create_exchange(
                    source_id=account_id,
                    dest_id=counter_account_id,
                    amount=float(amount or 0),
                    rate=float(exchange_rate),
                    counter_amount=None,
                    note=note,
                    tx_date=tx_date,
                )
            else:
                tx_svc.create_transfer(
                    source_id=account_id,
                    dest_id=counter_account_id,
                    amount=float(amount or 0),
                    currency=None,
                    note=note,
                    tx_date=tx_date,
                    fee_amount=tmpl.get("fee_amount"),
                )
        else:
            category_id = overrides.get("category_id") or tmpl.get("category_id")
            tags = overrides.get("tags") if "tags" in overrides else tmpl.get("tags")
            va_id = (
                overrides.get("va_id") if "va_id" in overrides else tmpl.get("va_id")
            )
            fee_amount = (
                overrides.get("fee_amount")
                if "fee_amount" in overrides
                else tmpl.get("fee_amount")
            )
            tx_data: dict[str, Any] = {
                "type": tx_type,
                "amount": amount,
                "account_id": account_id,
                "date": tx_date,
                "recurring_rule_id": rule.id,
            }
            if category_id:
                tx_data["category_id"] = category_id
            if note:
                tx_data["note"] = note
            if tags:
                tx_data["tags"] = tags
            created_tx, _ = tx_svc.create(tx_data)
            if fee_amount or va_id:
                tx_svc.apply_post_create_logic(
                    created_tx,
                    fee_amount=float(fee_amount) if fee_amount else None,
                    va_id=va_id,
                    tx_date=tx_date,
                )

        next_date = self._advance_due_date(rule)
        self._update_next_due_date(rule.id, next_date)

        # Auto allocate to goals
        if tmpl.get("type") == "income":
            from virtual_accounts.models import VirtualAccount
            from virtual_accounts.services import VirtualAccountService

            linked_vas = VirtualAccount.objects.for_user(self.user_id).filter(
                account_id=account_id,
                is_archived=False,
                auto_allocate=True,
                monthly_target__isnull=False,
                monthly_target__gt=0,
            )

            if linked_vas.exists():
                va_svc = VirtualAccountService(self.user_id, self.tz)
                now = django_tz.now()
                note_text = tmpl.get("note", "Recurring Income")
                for va in linked_vas:
                    try:
                        va_svc.direct_allocate(
                            va_id=str(va.id),
                            amount=float(va.monthly_target),
                            note=f"Auto-allocated from {note_text}",
                            allocated_at=now,
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to auto-allocate for rule %s to va %s: %s",
                            rule.id,
                            va.id,
                            str(e),
                        )

    def _advance_due_date(self, rule: RecurringRulePending) -> date:
        """Calculate next due date based on frequency.

        Weekly: +7 days
        Biweekly: +14 days
        Monthly: +1 month
        Quarterly: +3 months
        Yearly: +1 year
        """
        current: date = rule.next_due_date
        freq: str = rule.frequency
        if freq == "weekly":
            return current + timedelta(days=7)
        if freq == "biweekly":
            return current + timedelta(days=14)
        if freq == "monthly":
            return current + relativedelta(months=1)
        if freq == "quarterly":
            return current + relativedelta(months=3)
        if freq == "yearly":
            return current + relativedelta(years=1)
        # Default to monthly
        return current + relativedelta(months=1)

    def get_calendar_data(
        self, year: int, month: int, currency: str = ""
    ) -> list[dict[str, Any]]:
        """Get all recurring rule occurrences for a specific month.

        Calculates occurrences by projecting active rules into the target month.
        """
        from core.dates import month_range

        start_date, end_date = month_range(date(year, month, 1))

        qs = self._qs().filter(is_active=True)
        if currency:
            # Django's JSONField supports __ lookup
            qs = qs.filter(template_transaction__currency=currency)

        rules = qs
        occurrences = []

        for rule_inst in rules:
            rule = _instance_to_rule(rule_inst)
            view_data = self.rule_to_view(rule)

            # Project occurrences into the month
            current = rule.next_due_date

            # If next_due_date is before start_date, advance it until it's >= start_date
            # (only for projection purposes, not persisting)
            while current < start_date:
                # To avoid infinite loop for misconfigured rules, we limit iterations
                # or just check if it will ever reach the month.
                prev = current
                current = self._advance_due_date(
                    RecurringRulePending(
                        id=rule.id,
                        user_id=rule.user_id,
                        template_transaction=rule.template_transaction,
                        frequency=rule.frequency,
                        day_of_month=rule.day_of_month,
                        next_due_date=current,
                        is_active=rule.is_active,
                        auto_confirm=rule.auto_confirm,
                        created_at=rule.created_at,
                        updated_at=rule.updated_at,
                    )
                )
                if current <= prev:
                    break  # Safety

            # Now find all occurrences in the month
            while current < end_date:
                if current >= start_date:
                    occ = view_data.copy()
                    occ["due_date"] = current
                    occ["day"] = current.day
                    occurrences.append(occ)

                prev = current
                current = self._advance_due_date(
                    RecurringRulePending(
                        id=rule.id,
                        user_id=rule.user_id,
                        template_transaction=rule.template_transaction,
                        frequency=rule.frequency,
                        day_of_month=rule.day_of_month,
                        next_due_date=current,
                        is_active=rule.is_active,
                        auto_confirm=rule.auto_confirm,
                        created_at=rule.created_at,
                        updated_at=rule.updated_at,
                    )
                )
                if current <= prev:
                    break  # Safety

        # Sort by date
        occurrences.sort(key=lambda x: x["due_date"])
        return occurrences

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

        source_name = "Unknown"
        if account_id:
            source_name = (
                Account.objects.filter(id=account_id)
                .values_list("name", flat=True)
                .first()
                or "Unknown"
            )

        counter_name = "Unknown"
        if counter_account_id:
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

    def _get_account_and_category_names(
        self, account_id: str, category_id: str | None
    ) -> dict[str, str]:
        """Look up account and category names for an expense/income rule.

        Args:
            account_id: source account UUID
            category_id: category UUID (optional)

        Returns:
            dict with keys: account_name, category_name (if applicable)
        """
        from accounts.models import Account
        from categories.models import Category

        if not account_id:
            return {"account_name": "Unknown"}

        account_name = (
            Account.objects.filter(id=account_id).values_list("name", flat=True).first()
            or "Unknown"
        )

        result = {"account_name": account_name}

        if category_id:
            category_name = (
                Category.objects.filter(id=category_id)
                .values_list("name", flat=True)
                .first()
            )
            if category_name:
                if isinstance(category_name, dict):
                    result["category_name"] = category_name.get(
                        "en", str(category_name)
                    )
                else:
                    result["category_name"] = str(category_name)

        return result

    def rule_to_view(self, rule: RecurringRulePending) -> dict[str, Any]:
        """Enrich a rule with display fields for templates.

        Combines rule metadata with template display formatting:
        - Core fields: id, user_id, frequency, next_due_date, etc.
        - Template display fields: note, amount_display, is_transfer
        - Transfer-specific fields: source_account_name, counter_account_name, fee_display
        - Expense/Income fields: account_name, category_name

        Extracts note and amount from JSONB template without re-querying.
        For transfers, performs additional DB lookup to fetch account names.
        For non-transfers, fetches account and category names.

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

        # Look up and add specific account/category names
        if template_display["is_transfer"]:
            account_names = self._get_account_names(
                tmpl.get("account_id", ""),
                tmpl.get("counter_account_id", ""),
            )
            result.update(account_names)
        else:
            meta = self._get_account_and_category_names(
                tmpl.get("account_id", ""),
                tmpl.get("category_id"),
            )
            result.update(meta)

        return result
