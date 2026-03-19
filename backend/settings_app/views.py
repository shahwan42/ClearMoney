"""
Settings views — Django equivalents of Go's Settings and ExportTransactions handlers.

Migrated from:
- internal/handler/pages.go:2598 (Settings)
- internal/handler/pages.go:2609 (ExportTransactions)
- internal/service/export.go (ExportTransactionsCSV)

Like Laravel's SettingsController or Django's function-based views.
"""

import csv
import logging
from datetime import datetime

from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render

from core.types import AuthenticatedRequest

logger = logging.getLogger(__name__)


def settings_page(request: AuthenticatedRequest) -> HttpResponse:
    """
    Render the settings page.

    GET /settings — shows dark mode toggle, CSV export form, push
    notifications toggle, quick links, and logout button.

    Equivalent of Go's PageHandler.Settings() in pages.go:2598.
    No server data needed — all interactivity is client-side JS.
    """
    logger.info("page viewed: settings, user=%s", request.user_email)
    return render(request, "settings_app/settings.html")


def export_transactions(request: AuthenticatedRequest) -> HttpResponse:
    """
    Export transactions as a CSV file download.

    GET /export/transactions?from=2026-01-01&to=2026-03-31

    Equivalent of Go's PageHandler.ExportTransactions() in pages.go:2609
    and ExportService.ExportTransactionsCSV() in export.go.

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
    # Raw SQL matches Go's repository.GetByDateRange() query
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT date, type, amount, currency, account_id,
                   COALESCE(category_id::text, ''), COALESCE(note, ''), created_at
            FROM transactions
            WHERE user_id = %s AND date >= %s AND date <= %s
            ORDER BY date DESC, created_at DESC
            """,
            [user_id, from_date, to_date],
        )
        rows = cursor.fetchall()

    # Build CSV response — same columns as Go's ExportTransactionsCSV
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f"attachment; filename=transactions_{from_str}_{to_str}.csv"
    )

    writer = csv.writer(response)
    # Header row matching Go's export.go
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

    for row in rows:
        date_val, tx_type, amount, currency, account_id, cat_id, note, created_at = row
        writer.writerow(
            [
                date_val.strftime("%Y-%m-%d")
                if hasattr(date_val, "strftime")
                else str(date_val),
                tx_type,
                f"{float(amount):.2f}",
                currency,
                str(account_id),
                cat_id,
                note,
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
