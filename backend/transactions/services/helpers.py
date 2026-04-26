"""Helper methods: batch create, smart defaults, VA allocation, dropdowns.

HelperMixin is mixed into TransactionService and relies on methods from
TransactionServiceBase (self.create, self.get_by_id, self.user_id, etc.).
"""

import logging
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce
from django.utils import timezone as django_tz

from accounts.models import Account
from categories.models import Category
from transactions.display import get_tx_amount_color_class, get_tx_indicator_color
from transactions.models import Transaction, VirtualAccountAllocation
from virtual_accounts.models import VirtualAccount

logger = logging.getLogger(__name__)


class HelperMixin:
    """Mixin providing batch, smart defaults, VA allocation, and dropdown queries."""

    # -------------------------------------------------------------------
    # Batch
    # -------------------------------------------------------------------

    def batch_create(self, items: list[dict[str, Any]]) -> tuple[int, int]:
        """Create multiple transactions. Returns (created_count, failed_count).

        Each item is processed independently; failures don't roll back successes.
        """
        created = 0
        failed = 0
        for item in items:
            try:
                self.create(item)  # type: ignore[attr-defined]
                created += 1
            except (ValueError, Exception) as e:
                logger.warning("batch item failed: %s", e)
                failed += 1
        return created, failed

    # -------------------------------------------------------------------
    # Smart Defaults
    # -------------------------------------------------------------------

    def get_smart_defaults(self, tx_type: str = "expense") -> dict[str, Any]:
        """Compute smart defaults for the entry form.

        Non-critical — returns empty defaults on error.
        """
        defaults: dict[str, Any] = {
            "last_account_id": "",
            "auto_category_id": "",
            "recent_category_ids": [],
        }
        try:
            uid = self.user_id  # type: ignore[attr-defined]

            # Last used account
            last_account = (
                Transaction.objects.for_user(uid)
                .filter(type__in=["expense", "income"])
                .order_by("-created_at")
                .values_list("account_id", flat=True)
                .first()
            )
            if last_account:
                defaults["last_account_id"] = str(last_account)

            # Top 20 categories ranked by usage frequency for this tx type
            recent_cats = (
                Transaction.objects.for_user(uid)
                .filter(type=tx_type, category_id__isnull=False)
                .values("category_id")
                .annotate(cnt=Count("id"))
                .order_by("-cnt")[:20]
            )
            defaults["recent_category_ids"] = [
                str(r["category_id"]) for r in recent_cats
            ]

            # Auto category (3+ consecutive)
            last_three = list(
                Transaction.objects.for_user(uid)
                .filter(type=tx_type, category_id__isnull=False)
                .order_by("-created_at")
                .values_list("category_id", flat=True)[:3]
            )
            if len(last_three) == 3:
                ids = [str(cid) for cid in last_three]
                if ids[0] == ids[1] == ids[2]:
                    defaults["auto_category_id"] = ids[0]
        except Exception:
            logger.debug("smart defaults failed (non-critical)", exc_info=True)

        return defaults

    # -------------------------------------------------------------------
    # Category Suggestion
    # -------------------------------------------------------------------

    def suggest_category(self, note_keyword: str) -> str | None:
        """Suggest a category based on note keyword frequency."""
        if not note_keyword or not note_keyword.strip():
            return None
        uid = self.user_id  # type: ignore[attr-defined]
        # Most-used category for transactions matching this keyword (case-insensitive)
        row = (
            Transaction.objects.for_user(uid)
            .filter(note__icontains=note_keyword, category_id__isnull=False)
            .values("category_id")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")
            .first()
        )
        return str(row["category_id"]) if row else None

    # -------------------------------------------------------------------
    # Virtual Account Allocation
    # -------------------------------------------------------------------

    def allocate_to_virtual_account(
        self, tx_id: str, va_id: str, amount: float
    ) -> None:
        """Allocate a transaction to a virtual account.

        Validates that the VA's account_id is null (any account) or matches
        the transaction's account.
        """
        uid = self.user_id  # type: ignore[attr-defined]

        # Validate VA ownership and account linkage
        va = (
            VirtualAccount.objects.for_user(uid)
            .filter(id=va_id)
            .values("id", "account_id", "current_balance")
            .first()
        )
        if not va:
            raise ValueError(f"Pot not found: {va_id}")

        va_account_id = str(va["account_id"]) if va["account_id"] else None
        tx = self.get_by_id(tx_id)  # type: ignore[attr-defined]
        if not tx:
            raise ValueError(f"Transaction not found: {tx_id}")

        if va_account_id and va_account_id != tx["account_id"]:
            raise ValueError("Pot is linked to a different account")

        with transaction.atomic():
            VirtualAccountAllocation.objects.create(
                virtual_account_id=va_id,
                transaction_id=tx_id,
                amount=amount,
            )
            # Atomic F() update — increment cached VA balance without re-reading
            VirtualAccount.objects.for_user(uid).filter(id=va_id).update(
                current_balance=F("current_balance") + Decimal(str(amount)),
                updated_at=django_tz.now(),
            )

    def deallocate_from_virtual_accounts(self, tx_id: str) -> None:
        """Remove all virtual account allocations for a transaction."""
        uid = self.user_id  # type: ignore[attr-defined]

        # Get all allocations for this transaction, joined with VA for user check
        allocations = list(
            VirtualAccountAllocation.objects.filter(
                transaction_id=tx_id,
                virtual_account__user_id=uid,
            ).values_list("virtual_account_id", "amount")
        )

        if allocations:
            with transaction.atomic():
                now = django_tz.now()
                for va_id, alloc_amount in allocations:
                    # Atomic F() update — reverse each allocation's balance impact
                    VirtualAccount.objects.for_user(uid).filter(id=va_id).update(
                        current_balance=F("current_balance")
                        - Decimal(str(float(alloc_amount))),
                        updated_at=now,
                    )
                VirtualAccountAllocation.objects.filter(
                    transaction_id=tx_id,
                    virtual_account__user_id=uid,
                ).delete()

    def get_allocation_for_tx(self, tx_id: str) -> str | None:
        """Get the virtual account ID allocated to a transaction, if any."""
        result = (
            VirtualAccountAllocation.objects.filter(transaction_id=tx_id)
            .values_list("virtual_account_id", flat=True)
            .first()
        )
        return str(result) if result else None

    def apply_post_create_logic(
        self,
        tx: dict[str, Any],
        fee_amount: float | None = None,
        va_id: str | None = None,
        tx_date: Any = None,
    ) -> None:
        """Centralized logic for post-transaction creation tasks:
        1. Create or update optional linked fee transaction.
        2. Allocate/Reallocate to virtual account.
        """
        # 1. Linked Fee (handles add, update, and remove)
        self.update_fee_for_transaction(  # type: ignore[attr-defined]
            tx_id=tx["id"],
            fee_amount=fee_amount,
            tx_date=tx_date,
        )

        # 2. Virtual Account Allocation
        if va_id:
            alloc_amount = float(tx["amount"])
            if tx["type"] == "expense":
                alloc_amount = -alloc_amount

            # If this is an update, we might need to deallocate first
            # (But this method is designed for 'post-create' or 'unified update')
            old_va_id = self.get_allocation_for_tx(tx["id"])
            if old_va_id != va_id:
                if old_va_id:
                    self.deallocate_from_virtual_accounts(tx["id"])
                if va_id:
                    try:
                        self.allocate_to_virtual_account(tx["id"], va_id, alloc_amount)
                    except ValueError:
                        pass
        elif va_id == "" or va_id is None:
            # Handle explicit deallocation if va_id was provided as empty string
            old_va_id = self.get_allocation_for_tx(tx["id"])
            if old_va_id:
                self.deallocate_from_virtual_accounts(tx["id"])

    # -------------------------------------------------------------------
    # Helpers for views
    # -------------------------------------------------------------------

    def get_accounts(self, tx_type: str | None = None) -> list[dict[str, Any]]:
        """Get non-dormant accounts for dropdowns.

        When ``tx_type`` is provided, usage ranking is scoped to that transaction
        type. Callers without a selected type retain the global usage ordering.
        """
        uid = self.user_id  # type: ignore[attr-defined]
        usage_filter = Q(transactions__user_id=uid)
        if tx_type:
            usage_filter &= Q(transactions__type=tx_type)

        rows = (
            Account.objects.for_user(uid)
            .filter(is_dormant=False)
            .annotate(tx_count=Count("transactions", filter=usage_filter))
            .order_by("-tx_count", "display_order", "name")
            .values(
                "id",
                "name",
                "currency",
                "current_balance",
                "type",
                "institution__name",
                "institution__icon",
                "institution__color",
            )
        )
        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "currency": r["currency"],
                "current_balance": float(r["current_balance"]),
                "type": r["type"],
                "institution_name": r["institution__name"] or "",
                "institution_icon": r["institution__icon"] or "",
                "institution_color": r["institution__color"] or "",
            }
            for r in rows
        ]

    def get_categories(self, cat_type: str | None = None) -> list[dict[str, Any]]:
        """Get categories sorted by usage count (most used first), then name."""
        uid = self.user_id  # type: ignore[attr-defined]
        usage_sq = Subquery(
            Transaction.objects.filter(category_id=OuterRef("id"), user_id=uid)
            .values("category_id")
            .annotate(cnt=Count("id"))
            .values("cnt")[:1]
        )
        qs = Category.objects.for_user(uid).filter(is_archived=False)
        if cat_type:
            qs = qs.filter(type=cat_type)
        rows = (
            qs.annotate(
                usage_count=Coalesce(usage_sq, Value(0)),
                name_en=KeyTextTransform("en", "name"),
            )
            .order_by("-usage_count", "name_en")
            .values("id", "name", "type", "icon")
        )
        return [
            {
                "id": str(r["id"]),
                "name": r["name"].get("en", "")
                if isinstance(r["name"], dict)
                else r["name"],
                "type": r["type"],
                "icon": r["icon"],
            }
            for r in rows
        ]

    def get_virtual_accounts(self) -> list[dict[str, Any]]:
        """Get non-archived virtual accounts for allocation dropdown."""
        uid = self.user_id  # type: ignore[attr-defined]
        rows = (
            VirtualAccount.objects.for_user(uid)
            .filter(is_archived=False)
            .order_by("name")
            .values(
                "id",
                "name",
                "account_id",
                "target_amount",
                "current_balance",
                "account__currency",
            )
        )
        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "account_id": str(r["account_id"]) if r["account_id"] else None,
                "target_amount": float(r["target_amount"]) if r["target_amount"] else 0,
                "current_balance": (
                    float(r["current_balance"]) if r["current_balance"] else 0
                ),
                "currency": r["account__currency"],
            }
            for r in rows
        ]

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Global search across transactions for the current user.

        Matches against:
        - note (case-insensitive substring)
        - amount (cast to text, prefix/substring match)
        - category name in English (case-insensitive substring)

        Uses the same enriched raw-SQL pattern as ``get_filtered_enriched``
        (window-function running balance, account/category JOIN) so the returned
        dicts are compatible with ``_transaction_row.html``.

        Args:
            query: The search string (should be non-empty; caller must strip/validate).
            limit: Maximum number of results to return (default 20).

        Returns:
            List of enriched transaction dicts ordered by date DESC, created_at DESC.
        """
        from django.db import connection

        stripped = (query or "").strip()
        if not stripped or limit <= 0:
            return []

        uid = self.user_id  # type: ignore[attr-defined]
        pattern = f"%{stripped}%"

        sql = """
            SELECT sub.id, sub.user_id, sub.type, sub.amount, sub.currency, sub.account_id,
                sub.counter_account_id, sub.category_id, sub.date, sub.time, sub.note,
                sub.tags, sub.exchange_rate, sub.counter_amount,
                sub.person_id, sub.linked_transaction_id,
                sub.recurring_rule_id, sub.balance_delta, sub.created_at, sub.updated_at,
                sub.account_name, sub.category_name, sub.category_icon, sub.running_balance
            FROM (
                SELECT t.id, t.user_id, t.type, t.amount, t.currency, t.account_id,
                    t.counter_account_id, t.category_id, t.date, t.time, t.note,
                    (SELECT ARRAY_AGG(tg.name) FROM tags tg
                     JOIN transactions_tags ttg ON tg.id = ttg.tag_id
                     WHERE ttg.transaction_id = t.id) as tags,
                    t.exchange_rate, t.counter_amount,
                    t.person_id, t.linked_transaction_id,
                    t.recurring_rule_id, t.balance_delta, t.created_at, t.updated_at,
                    a.name AS account_name,
                    c.name->>'en' AS category_name,
                    c.icon AS category_icon,
                    a.current_balance - COALESCE(
                        SUM(t.balance_delta) OVER (
                            PARTITION BY t.account_id
                            ORDER BY t.date DESC, t.created_at DESC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                        ), 0
                    ) AS running_balance
                FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.user_id = %s
            ) sub
            WHERE (
                sub.note ILIKE %s
                OR sub.amount::text ILIKE %s
                OR sub.category_name ILIKE %s
            )
            ORDER BY sub.date DESC, sub.created_at DESC
            LIMIT %s
        """
        params = [uid, pattern, pattern, pattern, limit]

        cols = [
            "id",
            "user_id",
            "type",
            "amount",
            "currency",
            "account_id",
            "counter_account_id",
            "category_id",
            "date",
            "time",
            "note",
            "tags",
            "exchange_rate",
            "counter_amount",
            "person_id",
            "linked_transaction_id",
            "recurring_rule_id",
            "balance_delta",
            "created_at",
            "updated_at",
            "account_name",
            "category_name",
            "category_icon",
            "running_balance",
        ]

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        results = [self._scan_tx_row(row, cols) for row in rows]  # type: ignore[attr-defined]
        # Annotate with display fields so _transaction_row.html renders correctly
        from decimal import Decimal

        for tx in results:
            tx["indicator_color"] = get_tx_indicator_color(tx.get("type", ""))
            balance_delta_raw = tx.get("balance_delta")
            bd = Decimal(balance_delta_raw) if balance_delta_raw is not None else None
            tx["amount_color_class"] = get_tx_amount_color_class(tx.get("type", ""), bd)
        return results
