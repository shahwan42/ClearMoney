"""
Salary wizard views — page handlers for /salary*.

Port of Go's PageHandler salary methods (pages.go:1766–1903).
Like Laravel's SalaryWizardController — handles the multi-step HTMX wizard:
  Step 1: Salary amount, USD/EGP account selection, date
  Step 2: Exchange rate input with live EGP calculation
  Step 3: Allocate to EGP accounts with remainder tracking
  Confirm: Create all transactions atomically, show success

HTMX pattern: each step POST returns the next step's HTML partial,
which HTMX swaps into #salary-wizard. No page refresh needed.
"""

import logging
from datetime import datetime
from typing import Any

from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from salary.services import SalaryAllocation, SalaryDistribution, SalaryService

logger = logging.getLogger(__name__)


def _svc(request: AuthenticatedRequest) -> SalaryService:
    """Create a SalaryService for the authenticated user."""
    return SalaryService(request.user_id, request.tz)


def _get_accounts(request: AuthenticatedRequest) -> list[dict[str, Any]]:
    """Fetch active, non-dormant accounts for the form dropdowns."""
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, name, currency
               FROM accounts
               WHERE user_id = %s AND is_dormant = false
               ORDER BY display_order, name""",
            [request.user_id],
        )
        return [
            {"id": str(row[0]), "name": row[1], "currency": row[2]}
            for row in cursor.fetchall()
        ]


def _parse_float(value: str) -> float:
    """Parse a form value to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


@general_rate
@require_http_methods(["GET"])
def salary_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /salary — render the salary wizard page with step 1.

    Port of Go's PageHandler.Salary (pages.go:1766).
    """
    logger.info("page viewed: salary, user=%s", request.user_email)
    accounts = _get_accounts(request)
    today = datetime.now(request.tz).date()

    return render(
        request,
        "salary/salary.html",
        {
            "accounts": accounts,
            "today": today,
            "active_tab": "more",
        },
    )


@general_rate
@require_http_methods(["POST"])
def salary_step2(request: AuthenticatedRequest) -> HttpResponse:
    """POST /salary/step2 — process step 1, render exchange rate form.

    Port of Go's PageHandler.SalaryStep2 (pages.go:1778).
    """
    salary_usd = _parse_float(request.POST.get("salary_usd", ""))
    if salary_usd <= 0:
        return HttpResponse(
            '<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">'
            "Salary amount must be positive</div>",
            status=400,
        )

    return render(
        request,
        "salary/_step2.html",
        {
            "salary_usd": salary_usd,
            "usd_account_id": request.POST.get("usd_account_id", ""),
            "egp_account_id": request.POST.get("egp_account_id", ""),
            "date": request.POST.get("date", ""),
        },
    )


@general_rate
@require_http_methods(["POST"])
def salary_step3(request: AuthenticatedRequest) -> HttpResponse:
    """POST /salary/step3 — process step 2, render allocation form.

    Port of Go's PageHandler.SalaryStep3 (pages.go:1803).
    """
    salary_usd = _parse_float(request.POST.get("salary_usd", ""))
    exchange_rate = _parse_float(request.POST.get("exchange_rate", ""))
    salary_egp = salary_usd * exchange_rate

    # Filter to EGP accounts only for allocation targets
    accounts = _get_accounts(request)
    egp_accounts = [a for a in accounts if a["currency"] == "EGP"]

    egp_account_id = request.POST.get("egp_account_id", "")

    return render(
        request,
        "salary/_step3.html",
        {
            "salary_usd": salary_usd,
            "exchange_rate": exchange_rate,
            "salary_egp": salary_egp,
            "usd_account_id": request.POST.get("usd_account_id", ""),
            "egp_account_id": egp_account_id,
            "date": request.POST.get("date", ""),
            "egp_accounts": egp_accounts,
        },
    )


@general_rate
@require_http_methods(["POST"])
def salary_confirm(request: AuthenticatedRequest) -> HttpResponse:
    """POST /salary/confirm — create all salary transactions atomically.

    Port of Go's PageHandler.SalaryConfirm (pages.go:1844).
    Collects allocations from form fields named alloc_<account_id>.
    """
    salary_usd = _parse_float(request.POST.get("salary_usd", ""))
    exchange_rate = _parse_float(request.POST.get("exchange_rate", ""))

    # Parse date
    tx_date = None
    date_str = request.POST.get("date", "")
    if date_str:
        try:
            tx_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Collect allocations from alloc_<account_id> fields
    allocations: list[SalaryAllocation] = []
    for key in request.POST:
        if not key.startswith("alloc_"):
            continue
        account_id = key.removeprefix("alloc_")
        amount = _parse_float(request.POST.get(key, ""))
        if amount > 0:
            allocations.append(SalaryAllocation(account_id=account_id, amount=amount))

    dist = SalaryDistribution(
        salary_usd=salary_usd,
        exchange_rate=exchange_rate,
        usd_account_id=request.POST.get("usd_account_id", ""),
        egp_account_id=request.POST.get("egp_account_id", ""),
        allocations=allocations,
        tx_date=tx_date,
    )

    svc = _svc(request)
    try:
        result = svc.distribute(dist)
    except ValueError as e:
        return HttpResponse(
            f'<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">{e}</div>',
            status=400,
        )

    return render(
        request,
        "salary/_success.html",
        {
            "salary_usd": result.salary_usd,
            "exchange_rate": result.exchange_rate,
            "salary_egp": result.salary_egp,
            "alloc_count": result.alloc_count,
        },
    )
