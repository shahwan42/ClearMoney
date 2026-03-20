"""Reports views — monthly spending breakdown and income vs expenses charts.

Thin view that parses query params and delegates to reports.services.
"""

import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from reports.services import get_monthly_report

logger = logging.getLogger(__name__)


@general_rate
def reports_page(request: AuthenticatedRequest) -> HttpResponse:
    """Render the monthly reports page.

    GET /reports?year=2026&month=3&currency=EGP&account_id=xxx
    """
    logger.info("page viewed: reports, user=%s", request.user_email)

    now = timezone.localtime()
    year = now.year
    month = now.month

    year_str = request.GET.get("year", "")
    month_str = request.GET.get("month", "")
    if year_str.isdigit():
        year = int(year_str)
    if month_str.isdigit() and 1 <= int(month_str) <= 12:
        month = int(month_str)

    account_id = request.GET.get("account_id", "")
    currency = request.GET.get("currency", "")

    report = get_monthly_report(request.user_id, year, month, account_id, currency)

    return render(request, "reports/reports.html", {"data": report})
