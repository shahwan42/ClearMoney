"""
Settings views — page handlers for /settings and /export/transactions.

Like Laravel's SettingsController or Django's function-based views.
"""

import csv
import logging
from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import render

from core.models import Transaction
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest

logger = logging.getLogger(__name__)


@general_rate
def settings_page(request: AuthenticatedRequest) -> HttpResponse:
    """
    Render the settings page.

    GET /settings — shows dark mode toggle, CSV export form, push
    notifications toggle, quick links, and logout button.

    No server data needed — all interactivity is client-side JS.
    """
    logger.info("page viewed: settings, user=%s", request.user_email)
    return render(request, "settings_app/settings.html")


@general_rate
def export_transactions(request: AuthenticatedRequest) -> HttpResponse:
    """
    Export transactions as a CSV file download.

    GET /export/transactions?from=2026-01-01&to=2026-03-31

    The Content-Disposition header triggers a browser file download.
    Like Laravel's Response::download() or Django's StreamingHttpResponse.
    """
    user_id = request.user_id
    from_str = request.GET.get("from", "")
    to_str = request.GET.get("to", "")

    # Validate date parameters
    try:
        from_date = datetime.strptime(from_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        logger.warning(
            "export: invalid date params, from=%s, to=%s, user=%s",
            from_str,
            to_str,
            request.user_email,
        )
        return HttpResponse("Invalid 'from' or 'to' date", status=400)

    # Query transactions in date range for this user
    qs = (
        Transaction.objects.for_user(user_id)
        .filter(date__gte=from_date, date__lte=to_date)
        .order_by("-date", "-created_at")
        .values(
            "date",
            "type",
            "amount",
            "currency",
            "account_id",
            "category_id",
            "note",
            "created_at",
        )
    )

    # Build CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f"attachment; filename=transactions_{from_str}_{to_str}.csv"
    )

    writer = csv.writer(response)
    writer.writerow(
        [
            "Date",
            "Type",
            "Amount",
            "Currency",
            "Account ID",
            "Category ID",
            "Note",
            "Created At",
        ]
    )

    rows = list(qs)  # evaluate once so len(rows) below doesn't re-query
    for row in rows:
        date_val = row["date"]
        created_at = row["created_at"]
        writer.writerow(
            [
                date_val.strftime("%Y-%m-%d")
                if hasattr(date_val, "strftime")
                else str(date_val),
                row["type"],
                f"{float(row['amount']):.2f}",
                row["currency"],
                str(row["account_id"]),
                str(row["category_id"]) if row["category_id"] else "",
                row["note"] or "",
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at),
            ]
        )

    row_count = len(rows)
    logger.info(
        "export.csv_downloaded: rows=%d, from=%s, to=%s, user=%s",
        row_count,
        from_str,
        to_str,
        request.user_email,
    )
    return response
