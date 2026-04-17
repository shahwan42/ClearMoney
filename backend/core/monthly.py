"""Monthly summary helpers — shared between dashboard.services and reports.services."""

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from core.dates import month_range
from transactions.models import Transaction


def get_month_summary(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> dict[str, Any]:
    """Get income and expense totals for a single month."""
    start_date, end_date = month_range(date(year, month, 1))

    qs = Transaction.objects.for_user(user_id).filter(
        date__gte=start_date,
        date__lt=end_date,
    )

    if account_id:
        qs = qs.filter(account_id=account_id)
    if currency:
        qs = qs.filter(currency=currency)

    result = qs.aggregate(
        income=Coalesce(Sum("amount", filter=Q(type="income")), Decimal(0)),
        expenses=Coalesce(Sum("amount", filter=Q(type="expense")), Decimal(0)),
    )

    income = float(result["income"])
    expenses = float(result["expenses"])
    month_name = date(year, month, 1).strftime("%B")

    return {
        "year": year,
        "month": month,
        "month_name": month_name,
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
    }
