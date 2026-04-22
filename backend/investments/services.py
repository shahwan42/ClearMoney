"""
Investment service — CRUD + validation for investment portfolio tracking.

Like Laravel's InvestmentService — contains validation, ORM queries,
and structured logging for all investment mutations.

Key design: valuation is computed (units * last_unit_price), never stored.
"""

import logging
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone as django_tz

from auth_app.currency import resolve_user_currency_choice
from investments.models import Investment

logger = logging.getLogger(__name__)


class InvestmentService:
    """Handles investment CRUD — combined validation + repository logic.

    Like Laravel's InvestmentService wrapping Eloquent queries.
    All queries scoped to self.user_id for multi-user isolation.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return Investment.objects.for_user(self.user_id)

    def get_all(self) -> list[dict[str, Any]]:
        """Fetch all investments ordered by platform, fund name.

        Returns dicts with a computed 'valuation' field.
        """
        rows = (
            self._qs()
            .order_by("platform", "fund_name")
            .values(
                "id",
                "platform",
                "fund_name",
                "units",
                "last_unit_price",
                "currency",
                "last_updated",
                "created_at",
                "updated_at",
            )
        )
        return [
            {
                "id": str(row["id"]),
                "platform": row["platform"],
                "fund_name": row["fund_name"],
                "units": float(row["units"]),
                "last_unit_price": float(row["last_unit_price"]),
                "currency": row["currency"],
                "last_updated": row["last_updated"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "valuation": float(row["units"]) * float(row["last_unit_price"]),
            }
            for row in rows
        ]

    def get_total_valuation(self) -> float:
        """Compute total portfolio value: SUM(units * last_unit_price).

        Returns 0.0 for empty portfolios.
        """
        # Aggregate: SUM(units * last_unit_price) across all holdings
        result = self._qs().aggregate(
            total=Coalesce(
                Sum(
                    # ExpressionWrapper needed to multiply two model fields in-DB
                    ExpressionWrapper(
                        F("units") * F("last_unit_price"),
                        output_field=DecimalField(),
                    )
                ),
                Decimal(0),
            )
        )
        return float(result["total"])

    def create(self, data: dict[str, Any]) -> str:
        """Create a new investment holding.

        Validates inputs, applies defaults, inserts, and logs.
        Raises ValueError for validation failures.
        Returns the new investment ID.
        """
        fund_name = (data.get("fund_name") or "").strip()
        if not fund_name:
            raise ValueError("Fund name is required")

        units = float(data.get("units", 0))
        if units <= 0:
            raise ValueError("Units must be positive")

        unit_price = float(data.get("unit_price", 0))
        if unit_price <= 0:
            raise ValueError("Unit price must be positive")

        platform = (data.get("platform") or "").strip() or "Thndr"
        currency = resolve_user_currency_choice(self.user_id, data.get("currency"))

        inv = Investment.objects.create(
            user_id=self.user_id,
            platform=platform,
            fund_name=fund_name,
            units=units,
            last_unit_price=unit_price,
            currency=currency,
            last_updated=django_tz.now(),
        )

        new_id = str(inv.id)
        logger.info(
            "investment.created id=%s currency=%s user=%s",
            new_id,
            currency,
            self.user_id,
        )
        return new_id

    def update_valuation(self, investment_id: str, unit_price: float) -> None:
        """Update the unit price (NAV) for an investment.

        Also refreshes last_updated and updated_at timestamps.
        Raises ValueError if price is not positive.
        """
        if unit_price <= 0:
            raise ValueError("Unit price must be positive")

        now = django_tz.now()
        self._qs().filter(id=investment_id).update(
            last_unit_price=unit_price,
            last_updated=now,
            updated_at=now,
        )

        logger.info(
            "investment.valuation_updated id=%s user=%s",
            investment_id,
            self.user_id,
        )

    def delete(self, investment_id: str) -> None:
        """Delete an investment holding."""
        self._qs().filter(id=investment_id).delete()

        logger.info(
            "investment.deleted id=%s user=%s",
            investment_id,
            self.user_id,
        )
