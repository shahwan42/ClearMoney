"""
Accounts & Institutions service layer — business logic and ORM queries.

Like Django's fat-model or service-layer pattern. Uses the Django ORM with
``Model.objects.for_user(uid)`` for user-scoped queries. One function remains
as raw SQL: ``get_statement_data`` (complex period queries).
"""

import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce
from django.utils import timezone as django_tz
from django.utils.translation import gettext, gettext_lazy

from accounts.models import Account, AccountSnapshot, Institution
from accounts.types import (
    AccountDropdownItem,
    AccountSummary,
    HealthWarning,
    NetWorthSummary,
)
from auth_app.currency import get_user_active_currency_codes
from core.billing import (
    BillingCycleInfo,
    get_billing_cycle_info,
    get_credit_card_utilization,
    interest_free_remaining,
    parse_billing_cycle,
)
from core.dates import month_range
from core.serializers import parse_jsonb
from recurring.models import RecurringRule
from transactions.display import get_tx_amount_color_class, get_tx_indicator_color
from transactions.models import Transaction
from transactions.services.utils import running_balance_annotation
from virtual_accounts.models import VirtualAccount

logger = logging.getLogger(__name__)

# Valid account types — validated in service layer
VALID_ACCOUNT_TYPES = {
    "savings",
    "current",
    "prepaid",
    "cash",
    "credit_card",
    "credit_limit",
}
CREDIT_ACCOUNT_TYPES = {"credit_card", "credit_limit"}
VALID_INSTITUTION_TYPES = {"bank", "fintech", "wallet"}
# Human-readable labels for auto-generated account names
ACCOUNT_TYPE_LABELS: dict[str, Any] = {
    "savings": gettext_lazy("Savings"),
    "current": gettext_lazy("Current"),
    "prepaid": gettext_lazy("Prepaid"),
    "cash": gettext_lazy("Cash"),
    "credit_card": gettext_lazy("Credit Card"),
    "credit_limit": gettext_lazy("Credit Limit"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_trimmed_name(value: str, field_name: str) -> str:
    """Trim whitespace, raise ValueError if empty."""
    trimmed = value.strip() if value else ""
    if not trimmed:
        raise ValueError(
            gettext("%(field_name)s is required") % {"field_name": field_name}
        )
    return trimmed


# ---------------------------------------------------------------------------
# InstitutionService
# ---------------------------------------------------------------------------


class InstitutionService:
    """Like Laravel's InstitutionService — validates input, executes ORM queries,
    logs mutations.
    """

    # Columns fetched for institution dicts
    _FIELDS = (
        "id",
        "name",
        "type",
        "color",
        "icon",
        "display_order",
        "created_at",
        "updated_at",
    )

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return Institution.objects.for_user(self.user_id)

    def _row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        """Convert a .values() row to an institution dict with stringified UUID."""
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "type": row["type"],
            "color": row["color"],
            "icon": row["icon"],
            "display_order": row["display_order"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_all(self) -> list[dict[str, Any]]:
        """All institutions ordered by display_order, name."""
        rows = self._qs().order_by("display_order", "name").values(*self._FIELDS)
        return [self._row_to_dict(row) for row in rows]

    def get_by_id(self, inst_id: str) -> dict[str, Any] | None:
        """Single institution by ID. Returns None if not found."""
        row = self._qs().filter(id=inst_id).values(*self._FIELDS).first()
        return self._row_to_dict(row) if row else None

    def create(
        self,
        name: str,
        inst_type: str,
        icon: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        """Create institution. Validates name and type.

        icon and color may be supplied from preset selection (e.g. "cib.svg", "#003DA5").
        """
        name = _require_trimmed_name(name, "institution name")
        if not inst_type:
            inst_type = "bank"
        if inst_type not in VALID_INSTITUTION_TYPES:
            raise ValueError(
                gettext("invalid institution type: %(type)s") % {"type": inst_type}
            )

        inst = Institution.objects.create(
            user_id=self.user_id,
            name=name,
            type=inst_type,
            color=color or None,
            icon=icon or None,
            display_order=0,
        )
        logger.info("institution.created type=%s user=%s", inst_type, self.user_id)
        return {
            "id": str(inst.id),
            "name": inst.name,
            "type": inst.type,
            "color": inst.color,
            "icon": inst.icon,
            "display_order": inst.display_order,
            "created_at": inst.created_at,
            "updated_at": inst.updated_at,
        }

    def update(self, inst_id: str, name: str, inst_type: str) -> dict[str, Any] | None:
        """Update institution name and type. Returns updated record or None."""
        name = _require_trimmed_name(name, "institution name")
        now = django_tz.now()
        updated = (
            self._qs()
            .filter(id=inst_id)
            .update(
                name=name,
                type=inst_type,
                updated_at=now,
            )
        )
        if not updated:
            return None
        logger.info("institution.updated id=%s user=%s", inst_id, self.user_id)
        row = self._qs().filter(id=inst_id).values(*self._FIELDS).first()
        return self._row_to_dict(row) if row else None

    def delete(self, inst_id: str) -> bool:
        """Delete institution (cascades to accounts). Returns True if deleted."""
        count, _ = self._qs().filter(id=inst_id).delete()
        deleted = bool(count > 0)
        if deleted:
            logger.info("institution.deleted id=%s user=%s", inst_id, self.user_id)
        return deleted

    def get_or_create(
        self,
        name: str,
        inst_type: str,
        icon: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        """Get existing institution by name+type (case-insensitive) or create new one.

        Used by the unified add-account form so the user never sees the institution
        creation step — the backend handles deduplication transparently.
        """
        name = _require_trimmed_name(name, "institution name")
        if inst_type not in VALID_INSTITUTION_TYPES:
            raise ValueError(
                gettext("invalid institution type: %(type)s") % {"type": inst_type}
            )
        row = (
            self._qs()
            .filter(name__iexact=name, type=inst_type)
            .values(*self._FIELDS)
            .first()
        )
        if row:
            return self._row_to_dict(row)
        return self.create(name, inst_type, icon=icon, color=color)

    def reorder(self, ids: list[str]) -> None:
        """Update display_order for a list of institution IDs."""
        now = django_tz.now()
        for i, inst_id in enumerate(ids):
            self._qs().filter(id=inst_id).update(display_order=i, updated_at=now)
        logger.info("institution.reordered count=%d user=%s", len(ids), self.user_id)


# ---------------------------------------------------------------------------
# AccountService
# ---------------------------------------------------------------------------


class AccountService:
    """Handles CRUD, dormant toggle, reorder, health config, balance history,
    transaction list, and virtual account queries for the account detail page.
    """

    # Columns fetched for full account dicts
    _FIELDS = (
        "id",
        "institution_id",
        "name",
        "type",
        "currency",
        "current_balance",
        "initial_balance",
        "credit_limit",
        "is_dormant",
        "display_order",
        "metadata",
        "health_config",
        "last_reconciled_at",
        "last_balance_check_at",
        "last_checked_balance",
        "last_balance_check_diff",
        "last_balance_check_status",
        "created_at",
        "updated_at",
    )

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return Account.objects.for_user(self.user_id)

    # --- Read operations ---

    def get_all(self) -> list[AccountSummary]:
        """All accounts ordered by display_order, name."""
        rows = self._qs().order_by("display_order", "name").values(*self._FIELDS)
        return [self._row_to_summary(row) for row in rows]

    def get_for_dropdown(
        self, *, include_balance: bool = False
    ) -> list[AccountDropdownItem]:
        """Active (non-dormant) accounts for form dropdowns, ordered by usage then display_order.

        Returns lightweight AccountDropdownItem with id, name, currency (and optionally
        current_balance). Much cheaper than get_all() for dropdown selects.
        """
        qs = (
            self._qs()
            .filter(is_dormant=False)
            .annotate(
                tx_count=Count(
                    "transactions", filter=Q(transactions__user_id=self.user_id)
                )
            )
            .order_by("-tx_count", "display_order", "name")
        )
        if include_balance:
            rows = qs.values("id", "name", "currency", "current_balance")
            return [
                AccountDropdownItem(
                    id=str(r["id"]),
                    name=r["name"],
                    currency=r["currency"],
                    current_balance=float(r["current_balance"]),
                )
                for r in rows
            ]
        rows = qs.values("id", "name", "currency")
        return [
            AccountDropdownItem(id=str(r["id"]), name=r["name"], currency=r["currency"])
            for r in rows
        ]

    def get_by_id(self, account_id: str) -> AccountSummary | None:
        """Single account by ID. Returns None if not found."""
        row = self._qs().filter(id=account_id).values(*self._FIELDS).first()
        return self._row_to_summary(row) if row else None

    def get_by_institution(self, institution_id: str) -> list[AccountSummary]:
        """Accounts for a specific institution."""
        rows = (
            self._qs()
            .filter(institution_id=institution_id)
            .order_by("display_order", "name")
            .values(*self._FIELDS)
        )
        return [self._row_to_summary(row) for row in rows]

    # --- Write operations ---

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create account. Validates institution, credit limit rules.

        Name is optional — auto-generates "{Institution} - {Type}" if blank.
        """
        raw_name = (data.get("name", "") or "").strip()
        institution_id = data.get("institution_id", "")
        if not institution_id:
            raise ValueError(gettext("institution_id is required"))

        acc_type = data.get("type", "").strip() if data.get("type") else ""
        if not acc_type:
            raise ValueError(gettext("Please select an account type"))
        if acc_type not in VALID_ACCOUNT_TYPES:
            raise ValueError(
                gettext("Invalid account type: %(type)s") % {"type": acc_type}
            )

        # Auto-generate name from institution + type if left blank
        if raw_name:
            name = raw_name
        else:
            institution = Institution.objects.get(id=institution_id)
            type_label = ACCOUNT_TYPE_LABELS.get(acc_type, acc_type)
            name = f"{institution.name} - {type_label}"

        allowed_currencies = set(get_user_active_currency_codes(self.user_id))
        currency = str(data.get("currency", "EGP")).upper()
        if currency not in allowed_currencies:
            raise ValueError(
                gettext("invalid currency: %(currency)s") % {"currency": currency}
            )

        credit_limit = data.get("credit_limit")
        if acc_type in CREDIT_ACCOUNT_TYPES and credit_limit is None:
            raise ValueError(
                gettext("credit_limit is required for %(type)s accounts")
                % {"type": acc_type}
            )
        if acc_type == "cash" and credit_limit is not None:
            raise ValueError(gettext("cash accounts cannot have a credit limit"))

        initial_balance = data.get("initial_balance", 0.0)

        account = Account.objects.create(
            user_id=self.user_id,
            institution_id=institution_id,
            name=name,
            type=acc_type,
            currency=currency,
            current_balance=initial_balance,
            initial_balance=initial_balance,
            credit_limit=credit_limit,
            is_dormant=False,
            display_order=0,
            metadata={},
        )

        logger.info(
            "account.created type=%s currency=%s user=%s",
            acc_type,
            currency,
            self.user_id,
        )
        return {
            "id": str(account.id),
            "institution_id": institution_id,
            "name": name,
            "type": acc_type,
            "currency": currency,
            "current_balance": float(initial_balance),
            "initial_balance": float(initial_balance),
            "credit_limit": float(credit_limit) if credit_limit is not None else None,
            "is_dormant": False,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        }

    def update(self, account_id: str, data: dict[str, Any]) -> AccountSummary | None:
        """Update account fields (not balance). Returns updated record or None."""
        raw_name = (data.get("name", "") or "").strip()
        acc_type = data.get("type", "current")
        allowed_currencies = set(get_user_active_currency_codes(self.user_id))
        currency = str(data.get("currency", "EGP")).upper()
        if currency not in allowed_currencies:
            raise ValueError(
                gettext("invalid currency: %(currency)s") % {"currency": currency}
            )
        credit_limit = data.get("credit_limit")
        now = django_tz.now()

        if raw_name:
            name = raw_name
        else:
            # Auto-generate name from institution + type if left blank
            account = (
                self._qs().filter(id=account_id).select_related("institution").first()
            )
            if not account:
                return None
            type_label = ACCOUNT_TYPE_LABELS.get(acc_type, acc_type)
            name = f"{account.institution.name} - {type_label}"

        updated = (
            self._qs()
            .filter(id=account_id)
            .update(
                name=name,
                type=acc_type,
                currency=currency,
                credit_limit=credit_limit,
                updated_at=now,
            )
        )
        if not updated:
            return None
        logger.info("account.updated id=%s user=%s", account_id, self.user_id)
        row = self._qs().filter(id=account_id).values(*self._FIELDS).first()
        return self._row_to_summary(row) if row else None

    def delete(self, account_id: str) -> None:
        """Delete account.

        Cleans up recurring rules referencing this account (BUG-012).
        Raises ObjectDoesNotExist if account not found.
        """
        RecurringRule.objects.for_user(self.user_id).filter(
            template_transaction__account_id=account_id
        ).delete()
        count, _ = self._qs().filter(id=account_id).delete()
        if count == 0:
            raise ObjectDoesNotExist(f"Account not found: {account_id}")
        logger.info("account.deleted id=%s user=%s", account_id, self.user_id)

    def toggle_dormant(self, account_id: str) -> bool:
        """Toggle dormant flag. Returns True if account found."""
        # Fetch-toggle-save pattern because queryset .update() can't do NOT on a field
        account = self._qs().filter(id=account_id).first()
        if account is None:
            return False
        account.is_dormant = not account.is_dormant
        account.updated_at = django_tz.now()
        account.save(update_fields=["is_dormant", "updated_at"])
        logger.info("account.dormant_toggled id=%s user=%s", account_id, self.user_id)
        return True

    def reorder(self, ids: list[str]) -> None:
        """Update display_order for a list of account IDs."""
        now = django_tz.now()
        for i, account_id in enumerate(ids):
            self._qs().filter(id=account_id).update(display_order=i, updated_at=now)
        logger.info("account.reordered count=%d user=%s", len(ids), self.user_id)

    def update_health_config(self, account_id: str, config: dict[str, Any]) -> None:
        """Save health constraints to account's health_config JSONB."""
        now = django_tz.now()
        self._qs().filter(id=account_id).update(health_config=config, updated_at=now)
        logger.info(
            "account.health_config_updated id=%s user=%s", account_id, self.user_id
        )

    # --- Account detail data ---

    def get_balance_history(self, account_id: str, days: int = 30) -> list[float]:
        """30-day balance history from account_snapshots for sparkline."""
        today = date.today()
        from_date = today - timedelta(days=days)
        rows = (
            AccountSnapshot.objects.for_user(self.user_id)
            .filter(account_id=account_id, date__gte=from_date, date__lte=today)
            .order_by("date")
            .values_list("balance", flat=True)
        )
        return [float(bal) for bal in rows]

    def get_utilization_history(
        self, account_id: str, credit_limit: float, days: int = 30
    ) -> list[float]:
        """30-day utilization trend from balance history. Returns list of 0-100 values."""
        history = self.get_balance_history(account_id, days)
        if not history or credit_limit <= 0:
            return []
        return [min(100.0, max(0.0, (-bal / credit_limit) * 100)) for bal in history]

    def get_recent_transactions(
        self, account_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Recent transactions with running balance for account detail page.

        Window function computes running balance per account. Filtering by
        account_id here is safe because the PARTITION key is also account_id —
        restricting to one account does not change the per-account window scope.
        """
        qs = (
            Transaction.objects.filter(user_id=self.user_id, account_id=account_id)
            .select_related("account", "category")
            .annotate(
                account_name=F("account__name"),
                category_name=KeyTextTransform("en", "category__name"),
                category_icon=F("category__icon"),
                running_balance=running_balance_annotation(),
            )
            .order_by("-date", "-created_at")[:limit]
        )

        return [
            {
                "id": str(t.id),
                "type": t.type,
                "amount": float(t.amount),
                "currency": t.currency,
                "account_id": str(t.account_id),
                "category_id": str(t.category_id) if t.category_id else None,
                "date": t.date,
                "note": t.note,
                "tags": list(t.tags.all()) if hasattr(t, "tags") else [],
                "balance_delta": float(t.balance_delta),
                "is_verified": t.is_verified,
                "created_at": t.created_at,
                "account_name": t.account_name,
                "category_name": t.category_name,
                "category_icon": t.category_icon,
                "running_balance": float(t.running_balance),
                # Display-layer colors (moved from template)
                "indicator_color": get_tx_indicator_color(t.type),
                "amount_color_class": get_tx_amount_color_class(
                    t.type, t.balance_delta
                ),
            }
            for t in qs
        ]

    def get_unverified_transactions(self, account_id: str) -> list[dict[str, Any]]:
        """Get all unverified transactions for an account."""
        qs = (
            Transaction.objects.filter(
                user_id=self.user_id, account_id=account_id, is_verified=False
            )
            .select_related("account", "category")
            .annotate(
                account_name=F("account__name"),
                category_name=KeyTextTransform("en", "category__name"),
                category_icon=F("category__icon"),
            )
            .order_by("-date", "-created_at")
        )

        return [
            {
                "id": str(t.id),
                "type": t.type,
                "amount": float(t.amount),
                "currency": t.currency,
                "account_id": str(t.account_id),
                "category_id": str(t.category_id) if t.category_id else None,
                "date": t.date,
                "note": t.note,
                "tags": list(t.tags.all()) if hasattr(t, "tags") else [],
                "balance_delta": float(t.balance_delta),
                "is_verified": t.is_verified,
                "account_name": t.account_name,
                "category_name": t.category_name,
                "category_icon": t.category_icon,
                "indicator_color": get_tx_indicator_color(t.type),
                "amount_color_class": get_tx_amount_color_class(
                    t.type, t.balance_delta
                ),
            }
            for t in qs
        ]

    def reconcile(self, account_id: str, verified_tx_ids: list[str]) -> None:
        """Mark transactions as verified and update account's last_reconciled_at."""
        now = django_tz.now()
        with transaction.atomic():
            Transaction.objects.for_user(self.user_id).filter(
                account_id=account_id, id__in=verified_tx_ids
            ).update(is_verified=True, updated_at=now)

            self._qs().filter(id=account_id).update(
                last_reconciled_at=now, updated_at=now
            )
        logger.info(
            "account.reconciled id=%s verified_count=%d user=%s",
            account_id,
            len(verified_tx_ids),
            self.user_id,
        )

    def record_balance_check(
        self, account_id: str, checked_balance: Decimal | float | str
    ) -> dict[str, float | str]:
        """Persist a user-entered balance check against the current app balance."""
        account = self._qs().filter(id=account_id).values("current_balance").first()
        if not account:
            raise ValueError(gettext("Account not found: %(id)s") % {"id": account_id})

        now = django_tz.now()
        current_balance = Decimal(str(account["current_balance"]))
        entered_balance = Decimal(str(checked_balance))
        difference = entered_balance - current_balance
        status = "matched" if abs(difference) < Decimal("0.01") else "mismatch"
        stored_difference = Decimal("0.00") if status == "matched" else difference

        self._qs().filter(id=account_id).update(
            last_balance_check_at=now,
            last_checked_balance=entered_balance,
            last_balance_check_diff=stored_difference,
            last_balance_check_status=status,
            last_reconciled_at=now,
            updated_at=now,
        )
        logger.info(
            "account.balance_check_saved id=%s status=%s diff=%s user=%s",
            account_id,
            status,
            stored_difference,
            self.user_id,
        )
        return {"difference": float(stored_difference), "status": status}

    def create_balance_correction(
        self, account_id: str, checked_balance: Decimal | float | str
    ) -> str:
        """Create an explicit balance correction transaction and mark the check matched."""
        account = (
            self._qs()
            .filter(id=account_id)
            .values("current_balance", "currency")
            .first()
        )
        if not account:
            raise ValueError(gettext("Account not found: %(id)s") % {"id": account_id})

        now = django_tz.now()
        current_balance = Decimal(str(account["current_balance"]))
        entered_balance = Decimal(str(checked_balance))
        difference = entered_balance - current_balance

        if abs(difference) < Decimal("0.01"):
            self.record_balance_check(account_id, entered_balance)
            return ""

        tx_type = "income" if difference > 0 else "expense"
        amount = abs(difference)
        note = gettext("Balance correction")

        with transaction.atomic():
            tx = Transaction.objects.create(
                user_id=self.user_id,
                type=tx_type,
                amount=amount,
                currency=account["currency"],
                account_id=account_id,
                date=now.date(),
                note=note,
                balance_delta=difference,
            )
            self._qs().filter(id=account_id).update(
                current_balance=F("current_balance") + difference,
                last_balance_check_at=now,
                last_checked_balance=entered_balance,
                last_balance_check_diff=Decimal("0.00"),
                last_balance_check_status="matched",
                last_reconciled_at=now,
                updated_at=now,
            )

        logger.info(
            "account.balance_correction_created id=%s tx=%s diff=%s user=%s",
            account_id,
            tx.id,
            difference,
            self.user_id,
        )
        return str(tx.id)

    def get_linked_virtual_accounts(self, account_id: str) -> list[dict[str, Any]]:
        """Virtual accounts linked to this bank account (non-archived)."""
        rows = (
            VirtualAccount.objects.for_user(self.user_id)
            .filter(account_id=account_id, is_archived=False)
            .order_by("display_order", "created_at")
            .values(
                "id",
                "name",
                "target_amount",
                "current_balance",
                "icon",
                "color",
                "is_archived",
                "exclude_from_net_worth",
                "display_order",
                "account_id",
                "account__currency",
            )
        )
        result = []
        for row in rows:
            target = float(row["target_amount"]) if row["target_amount"] else 0.0
            current = float(row["current_balance"]) if row["current_balance"] else 0.0
            progress = (current / target * 100) if target > 0 else 0.0
            result.append(
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "target_amount": target,
                    "current_balance": current,
                    "icon": row["icon"],
                    "color": row["color"],
                    "is_archived": row["is_archived"],
                    "exclude_from_net_worth": row["exclude_from_net_worth"],
                    "display_order": row["display_order"],
                    "account_id": str(row["account_id"]),
                    "currency": row["account__currency"],
                    "progress_pct": min(100.0, progress),
                }
            )
        return result

    def get_excluded_va_balance(self, account_id: str) -> float:
        """Total excluded VA balance for a bank account."""
        result = (
            VirtualAccount.objects.for_user(self.user_id)
            .filter(
                account_id=account_id,
                exclude_from_net_worth=True,
                is_archived=False,
            )
            .aggregate(total=Coalesce(Sum("current_balance"), Decimal("0")))
        )
        return float(result["total"])

    def get_detail_data(self, account_id: str) -> dict[str, Any]:
        """Assemble all data required for the account detail page.

        Encapsulates institution resolution, billing cycles, balance/utilization
        history, virtual accounts, and health checks.
        """
        account = self.get_by_id(account_id)
        if not account:
            return {}

        # Institution info
        inst_svc = InstitutionService(self.user_id, self.tz)
        inst = (
            inst_svc.get_by_id(account.institution_id)
            if account.institution_id
            else None
        )
        institution_name = inst["name"] if inst else ""

        # Billing cycle (credit cards only)
        billing_cycle = None
        if account.is_credit_type and account.metadata:
            cycle = parse_billing_cycle(account.metadata)
            if cycle:
                billing_cycle = get_billing_cycle_info(cycle[0], cycle[1], date.today())

        # Histories (sparklines)
        balance_history = self.get_balance_history(account_id)
        utilization = 0.0
        utilization_history: list[float] = []
        if account.is_credit_type:
            utilization = get_credit_card_utilization(
                account.current_balance, account.credit_limit
            )
            if account.credit_limit and account.credit_limit > 0:
                utilization_history = self.get_utilization_history(
                    account_id, account.credit_limit
                )

        # Virtual accounts and "Your Money"
        virtual_accounts = self.get_linked_virtual_accounts(account_id)
        excluded_va_balance = self.get_excluded_va_balance(account_id)
        your_money = account.current_balance - excluded_va_balance

        # Over-allocation warning
        total_va_balance = sum(va["current_balance"] for va in virtual_accounts)
        is_over_allocated = total_va_balance > account.current_balance

        # Recent transactions
        transactions = self.get_recent_transactions(account_id, limit=50)
        has_more = len(transactions) >= 50

        # UI Color helpers
        from accounts.display import (
            get_balance_color_class,
            get_utilization_color_hex,
            get_your_money_color_class,
        )

        return {
            "account": account,
            "institution_name": institution_name,
            "billing_cycle": billing_cycle,
            "balance_history": balance_history,
            "balance_color_class": get_balance_color_class(account.current_balance),
            "utilization": utilization,
            "utilization_color": get_utilization_color_hex(utilization),
            "utilization_history": utilization_history,
            "virtual_accounts": virtual_accounts,
            "excluded_va_balance": excluded_va_balance,
            "is_over_allocated": is_over_allocated,
            "your_money": your_money,
            "your_money_color_class": get_your_money_color_class(your_money),
            "health_config": account.health_config or {},
            "transactions": transactions,
            "has_more": has_more,
        }

    def get_add_form_context(self, institution_id: str = "") -> dict[str, Any]:
        """Generate common context for the add account form (presets, etc.)."""
        from accounts.institution_data import (
            EGYPTIAN_BANKS,
            EGYPTIAN_FINTECHS,
            WALLET_EXAMPLES,
        )

        preselected = None
        if institution_id:
            inst_svc = InstitutionService(self.user_id, self.tz)
            preselected = inst_svc.get_by_id(institution_id)

        import json

        return {
            "institution_id": institution_id if preselected else "",
            "preselected_institution": preselected,
            "presets_json": json.dumps(
                {
                    "bank": EGYPTIAN_BANKS,
                    "fintech": EGYPTIAN_FINTECHS,
                    "wallet": list(WALLET_EXAMPLES),
                }
            ),
            "account_type": "current",
            "account_currency": get_user_active_currency_codes(self.user_id)[0],
            "account_name": "",
            "account_balance": "",
            "account_credit_limit": "",
        }

    # --- Internal helpers ---

    def _row_to_summary(self, row: dict[str, Any]) -> AccountSummary:
        """Convert a .values() row to an AccountSummary with computed fields."""
        balance = float(row["current_balance"])
        credit_limit = (
            float(row["credit_limit"]) if row["credit_limit"] is not None else None
        )
        acc_type = row["type"]
        is_credit = acc_type in CREDIT_ACCOUNT_TYPES
        metadata = parse_jsonb(row["metadata"])
        health_config = parse_jsonb(row["health_config"]) or {}

        available_credit = None
        if is_credit and credit_limit is not None:
            available_credit = credit_limit + balance  # balance is negative for CC

        inst_id = row["institution_id"]
        return AccountSummary(
            id=str(row["id"]),
            institution_id=str(inst_id) if inst_id else None,
            name=row["name"],
            type=acc_type,
            currency=row["currency"],
            current_balance=balance,
            initial_balance=float(row["initial_balance"]),
            credit_limit=credit_limit,
            is_dormant=row["is_dormant"],
            display_order=row["display_order"],
            metadata=metadata,
            health_config=health_config,
            last_reconciled_at=row["last_reconciled_at"],
            last_balance_check_at=row["last_balance_check_at"],
            last_checked_balance=(
                float(row["last_checked_balance"])
                if row["last_checked_balance"] is not None
                else None
            ),
            last_balance_check_diff=(
                float(row["last_balance_check_diff"])
                if row["last_balance_check_diff"] is not None
                else None
            ),
            last_balance_check_status=row["last_balance_check_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_credit_type=is_credit,
            available_credit=available_credit,
        )


# ---------------------------------------------------------------------------
# Statement data
# ---------------------------------------------------------------------------


def _parse_statement_period(
    statement_day: int, due_day: int, t_date: date, period_str: str
) -> BillingCycleInfo:
    """Recompute billing cycle info when a specific YYYY-MM period is requested."""
    info = get_billing_cycle_info(statement_day, due_day, t_date)
    if not period_str:
        return info
    try:
        parts = period_str.split("-")
        year = int(parts[0])
        month = int(parts[1])
        ref_date = date(year, month, min(statement_day, 28))
        return get_billing_cycle_info(statement_day, due_day, ref_date)
    except (ValueError, IndexError):
        return info


def _fetch_statement_transactions(
    user_id: str, account_id: str, period_start: date, period_end: date
) -> list[dict[str, Any]]:
    """Query transactions within the statement period."""
    return [
        {
            "id": str(row["id"]),
            "type": row["type"],
            "amount": float(row["amount"]),
            "currency": row["currency"],
            "account_id": str(row["account_id"]),
            "date": row["date"],
            "note": row["note"],
            "balance_delta": float(row["balance_delta"]),
            "created_at": row["created_at"],
        }
        for row in (
            Transaction.objects.for_user(user_id)
            .filter(account_id=account_id, date__gte=period_start, date__lte=period_end)
            .order_by("-date", "-created_at")
            .values(
                "id",
                "type",
                "amount",
                "currency",
                "account_id",
                "date",
                "note",
                "balance_delta",
                "created_at",
            )
        )
    ]


def _calculate_opening_balance(
    transactions: list[dict[str, Any]], closing_balance: float
) -> tuple[float, float, float]:
    """Derive opening balance and spending/payment totals from transaction list."""
    total_spending = total_payments = 0.0
    for tx in transactions:
        if tx["balance_delta"] < 0:
            total_spending += -tx["balance_delta"]
        else:
            total_payments += tx["balance_delta"]
    opening_balance = closing_balance
    for tx in transactions:
        opening_balance -= tx["balance_delta"]
    return opening_balance, total_spending, total_payments


def _calculate_interest_free_period(p_end: date, t_date: date) -> tuple[int, bool]:
    """Compute interest-free days remaining and urgency flag."""
    return interest_free_remaining(p_end, t_date)


def _fetch_payment_history(user_id: str, account_id: str) -> list[dict[str, Any]]:
    """Fetch last 10 incoming payments/credits for the account."""
    return [
        {
            "id": str(row["id"]),
            "type": row["type"],
            "amount": float(row["amount"]),
            "currency": row["currency"],
            "account_id": str(row["account_id"]),
            "date": row["date"],
            "note": row["note"],
            "balance_delta": float(row["balance_delta"]),
            "created_at": row["created_at"],
        }
        for row in (
            Transaction.objects.for_user(user_id)
            .filter(
                Q(account_id=account_id) | Q(counter_account_id=account_id),
                balance_delta__gt=0,
                type__in=["income", "transfer"],
            )
            .order_by("-date", "-created_at")[:10]
            .values(
                "id",
                "type",
                "amount",
                "currency",
                "account_id",
                "date",
                "note",
                "balance_delta",
                "created_at",
            )
        )
    ]


def get_statement_data(
    account: AccountSummary | dict[str, Any],
    user_id: str,
    tz: ZoneInfo,
    period_str: str = "",
) -> dict[str, Any] | None:
    """Full CC statement: transactions, balances, interest-free period, payment history.

    Returns None if no billing cycle configured.
    Kept as raw SQL — complex period queries with multiple aggregations.
    """
    if isinstance(account, AccountSummary):
        account_id = account.id
        metadata = account.metadata
        current_balance = account.current_balance
    else:
        account_id = account["id"]
        metadata = account.get("metadata")
        current_balance = account["current_balance"]
    cycle = parse_billing_cycle(metadata)
    if not cycle:
        return None

    statement_day, due_day = cycle
    today = date.today()
    info = _parse_statement_period(statement_day, due_day, today, period_str)

    transactions = _fetch_statement_transactions(
        user_id, account_id, info.period_start, info.period_end
    )
    closing_balance = current_balance
    opening_balance, total_spending, total_payments = _calculate_opening_balance(
        transactions, closing_balance
    )
    remaining, is_urgent = _calculate_interest_free_period(info.period_end, today)
    payment_history = _fetch_payment_history(user_id, account_id)

    return {
        "account": account,
        "billing_cycle": info,
        "transactions": transactions,
        "opening_balance": opening_balance,
        "total_spending": total_spending,
        "total_payments": total_payments,
        "closing_balance": closing_balance,
        "interest_free_days": 55,
        "interest_free_remain": remaining,
        "interest_free_urgent": is_urgent,
        "payment_history": payment_history,
    }


# ============================================================================
# Cross-module functions (used by push notifications, dashboard, etc.)
# ============================================================================


def load_health_warnings(
    user_id: str,
    all_accounts: Sequence[AccountSummary | dict[str, Any]],
    tz: ZoneInfo,
    include_stale_reconciliation: bool = False,
) -> list[HealthWarning]:
    """Check account health constraints.

    Parses health_config JSONB and checks min_balance / min_monthly_deposit.
    Extracted from dashboard/services/widgets.py for reuse by push notifications.
    """
    warnings: list[HealthWarning] = []
    now = datetime.now(tz)
    t_date = now.date()
    m_start, _ = month_range(t_date)
    m_end = (m_start + timedelta(days=32)).replace(day=1)

    # Find which accounts have at least one transaction to avoid noise for new accounts
    acc_ids = [
        str(acc.id if isinstance(acc, AccountSummary) else acc["id"])
        for acc in all_accounts
    ]
    accounts_with_tx = set(
        map(
            str,
            Transaction.objects.filter(user_id=user_id, account_id__in=acc_ids)
            .values_list("account_id", flat=True)
            .distinct(),
        )
    )

    for acc in all_accounts:
        # Support both AccountSummary and dict[str, Any]
        if isinstance(acc, AccountSummary):
            if acc.is_dormant:
                continue
            acc_name = acc.name
            acc_id = acc.id
            current_balance = acc.current_balance
            health_config: dict[str, Any] | None = acc.health_config
            acc_created_at = acc.created_at
        else:
            if acc.get("is_dormant"):
                continue
            acc_name = acc["name"]
            acc_id = acc["id"]
            current_balance = acc["current_balance"]
            health_config = acc.get("health_config")
            acc_created_at = acc.get("created_at")

        cfg = parse_jsonb(health_config)
        if cfg:
            # Check minimum balance
            min_balance = cfg.get("min_balance")
            if min_balance is not None and Decimal(str(current_balance)) < Decimal(
                str(min_balance)
            ):
                warnings.append(
                    HealthWarning(
                        account_name=acc_name,
                        account_id=acc_id,
                        rule="min_balance",
                        message=gettext(
                            "%(name)s balance (%(balance)s) is below minimum (%(min)s)"
                        )
                        % {
                            "name": acc_name,
                            "balance": f"{Decimal(str(current_balance)):,.2f}",
                            "min": f"{Decimal(str(min_balance)):,.2f}",
                        },
                    )
                )

            # Check minimum monthly deposit
            min_deposit = cfg.get("min_monthly_deposit")
            if min_deposit is not None:
                # Total income for this account this month
                total_income = Transaction.objects.filter(
                    user_id=user_id,
                    account_id=acc_id,
                    type="income",
                    date__gte=m_start,
                    date__lt=m_end,
                ).aggregate(total=Coalesce(Sum("amount"), Decimal(0)))[
                    "total"
                ] or Decimal(0)

                if total_income < Decimal(str(min_deposit)):
                    warnings.append(
                        HealthWarning(
                            account_name=acc_name,
                            account_id=acc_id,
                            rule="min_monthly_deposit",
                            message=gettext(
                                "%(name)s is missing required monthly deposit (%(min)s)"
                            )
                            % {
                                "name": acc_name,
                                "min": f"{Decimal(str(min_deposit)):,.2f}",
                            },
                        )
                    )

        # Check reconciliation status (30 days) - always at the end
        if include_stale_reconciliation:
            if isinstance(acc, AccountSummary):
                last_balance_check_at = (
                    acc.last_balance_check_at or acc.last_reconciled_at
                )
            else:
                last_balance_check_at = acc.get("last_balance_check_at") or acc.get(
                    "last_reconciled_at"
                )

            if not last_balance_check_at:
                # Skip banner for accounts created within the last 30 days —
                # they haven't had time to need reconciliation yet.
                created_dt = acc_created_at
                if isinstance(created_dt, str):
                    created_dt = datetime.fromisoformat(
                        created_dt.replace("Z", "+00:00")
                    )
                account_age_days = (
                    (now - created_dt).days
                    if isinstance(created_dt, datetime)
                    else 0  # unknown age → treat as new
                )
                if (
                    account_age_days >= 30 and str(acc_id) in accounts_with_tx
                ) and account_age_days >= 0:
                    warnings.append(
                        HealthWarning(
                            account_name=acc_name,
                            account_id=acc_id,
                            rule="balance_check_missing",
                            message=gettext("%(name)s hasn't been checked yet")
                            % {"name": acc_name},
                        )
                    )
            else:
                if isinstance(last_balance_check_at, str):
                    last_balance_check_at = datetime.fromisoformat(
                        last_balance_check_at.replace("Z", "+00:00")
                    )

                assert isinstance(last_balance_check_at, datetime)
                if (now - last_balance_check_at).days >= 30:
                    warnings.append(
                        HealthWarning(
                            account_name=acc_name,
                            account_id=acc_id,
                            rule="balance_check_stale",
                            message=gettext(
                                "%(name)s hasn't been checked in %(days)d days"
                            )
                            % {
                                "name": acc_name,
                                "days": (now - last_balance_check_at).days,
                            },
                        )
                    )

    return warnings


# Credit account types (shared with dashboard)
CREDIT_ACCOUNT_TYPES = {"credit_card", "credit_limit"}


def compute_net_worth(all_accounts: list[dict[str, Any]]) -> NetWorthSummary:
    """Compute net worth breakdown from account balances.

    Pure function — no DB access. Sums balances and splits by currency/type.
    Extracted from dashboard/services/accounts.py for reuse.
    """
    summary = NetWorthSummary()

    for acc in all_accounts:
        balance = acc["current_balance"]
        currency = acc["currency"]
        summary.net_worth += balance

        # 1. Total by currency
        summary.totals_by_currency[currency] = (
            summary.totals_by_currency.get(currency, 0.0) + balance
        )

        # 2. Debt by currency (negative balances)
        if balance < 0:
            abs_bal = abs(balance)
            summary.debt_total += abs_bal
            summary.debt_by_currency[currency] = (
                summary.debt_by_currency.get(currency, 0.0) + abs_bal
            )

        # 3. Credit vs Cash — dormant accounts excluded from credit metrics
        if acc["type"] in CREDIT_ACCOUNT_TYPES and not acc.get("is_dormant"):
            summary.credit_used += balance  # negative for CCs (display negates)
            summary.credit_used_by_currency[currency] = (
                summary.credit_used_by_currency.get(currency, 0.0) + balance
            )
            limit = acc["credit_limit"]
            if limit is not None and limit > 0:
                # available = limit + balance (balance is negative, so this subtracts debt)
                avail = limit + balance
                summary.credit_avail += avail
                summary.credit_avail_by_currency[currency] = (
                    summary.credit_avail_by_currency.get(currency, 0.0) + avail
                )
        elif acc["type"] not in CREDIT_ACCOUNT_TYPES:
            # Liquid cash (positive non-credit balances)
            if balance > 0:
                summary.cash_by_currency[currency] = (
                    summary.cash_by_currency.get(currency, 0.0) + balance
                )

    return summary
