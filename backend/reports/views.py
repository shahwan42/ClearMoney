"""Reports views — monthly spending breakdown and income vs expenses charts.

Thin view that parses query params and delegates to reports.services.
"""

import logging
from datetime import date

from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

try:
    from weasyprint import HTML
except Exception:
    HTML = None

from auth_app.currency import resolve_user_currency_choice
from budgets.services import BudgetService
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from reports.services import get_monthly_report

logger = logging.getLogger(__name__)

PDF_AVAILABLE: bool = HTML is not None


@general_rate
@require_http_methods(["GET"])
def reports_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /reports — monthly summary page."""
    year_str = request.GET.get("year", "")
    month_str = request.GET.get("month", "")
    now = date.today()
    year = int(year_str) if year_str.isdigit() else now.year
    month = int(month_str) if month_str.isdigit() else now.month

    account_id = request.GET.get("account_id", "")
    try:
        currency = resolve_user_currency_choice(
            request.user_id, request.GET.get("currency", "")
        )
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)

    months = 6
    months_str = request.GET.get("months", "")
    if months_str.isdigit() and int(months_str) in [3, 6, 12]:
        months = int(months_str)

    report = get_monthly_report(
        request.user_id, year, month, account_id, currency, months=months
    )

    return render(
        request,
        "reports/reports.html",
        {"data": report, "pdf_available": PDF_AVAILABLE},
    )


@general_rate
@require_http_methods(["GET"])
def export_pdf_report(request: AuthenticatedRequest) -> HttpResponse:
    """GET /reports/export-pdf — generate and download monthly PDF report."""
    if HTML is None:
        return HttpResponse("PDF export is not available on this server.", status=503)

    year_str = request.GET.get("year", "")
    month_str = request.GET.get("month", "")
    now = date.today()
    year = int(year_str) if year_str.isdigit() else now.year
    month = int(month_str) if month_str.isdigit() else now.month

    account_id = request.GET.get("account_id", "")
    try:
        currency = resolve_user_currency_choice(
            request.user_id, request.GET.get("currency", "")
        )
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)

    # Always use 6 months for trends in PDF
    report_data = get_monthly_report(
        request.user_id, year, month, account_id, currency, months=6
    )

    # Budget status for the reported month
    budget_svc = BudgetService(request.user_id, request.tz)
    budgets = budget_svc.get_all_with_spending(target_date=date(year, month, 1))

    html_string = render_to_string(
        "reports/pdf_report.html",
        {"data": report_data, "today": now, "budgets": budgets},
    )

    pdf_file = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_file, content_type="application/pdf")
    filename = f"ClearMoney_Report_{year}_{month:02d}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response
