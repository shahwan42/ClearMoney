"""
Investment service — CRUD + validation for investment portfolio tracking.

Like Laravel's InvestmentService — contains validation, raw SQL queries,
and structured logging for all investment mutations.

Key design: valuation is computed (units × last_unit_price), never stored.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection

logger = logging.getLogger(__name__)


class InvestmentService:
    """Handles investment CRUD — combined validation + repository logic.

    Like Laravel's InvestmentService wrapping Eloquent queries.
    All queries scoped to self.user_id for multi-user isolation.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_all(self) -> list[dict[str, Any]]:
        """Fetch all investments ordered by platform, fund name.

        Returns dicts with a computed 'valuation' field.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, platform, fund_name, units, last_unit_price,
                       currency, last_updated, created_at, updated_at
                FROM investments
                WHERE user_id = %s
                ORDER BY platform, fund_name
                """,
                [self.user_id],
            )
            rows = cursor.fetchall()

        return [
            {
                "id": str(row[0]),
                "platform": row[1],
                "fund_name": row[2],
                "units": float(row[3]),
                "last_unit_price": float(row[4]),
                "currency": row[5],
                "last_updated": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "valuation": float(row[3]) * float(row[4]),
            }
            for row in rows
        ]

    def get_total_valuation(self) -> float:
        """Compute total portfolio value: SUM(units * last_unit_price).

        Returns 0.0 for empty portfolios (COALESCE handles NULL).
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(units * last_unit_price), 0)
                FROM investments
                WHERE user_id = %s
                """,
                [self.user_id],
            )
            row = cursor.fetchone()

        return float(row[0]) if row else 0.0

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
        currency = (data.get("currency") or "").strip() or "EGP"

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO investments
                    (user_id, platform, fund_name, units, last_unit_price, currency)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [self.user_id, platform, fund_name, units, unit_price, currency],
            )
            new_id = str(cursor.fetchone()[0])

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

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE investments
                SET last_unit_price = %s,
                    last_updated = NOW(),
                    updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                [unit_price, investment_id, self.user_id],
            )

        logger.info(
            "investment.valuation_updated id=%s user=%s",
            investment_id,
            self.user_id,
        )

    def delete(self, investment_id: str) -> None:
        """Delete an investment holding."""
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM investments WHERE id = %s AND user_id = %s",
                [investment_id, self.user_id],
            )

        logger.info(
            "investment.deleted id=%s user=%s",
            investment_id,
            self.user_id,
        )
