"""
Virtual account views — page handlers for /virtual-accounts/*.

Like Laravel's VirtualAccountController — handles the list page, detail page,
CRUD operations, direct allocations, and HTMX edit form.

Uses standard POST forms with redirects for mutations (create, archive, allocate)
and HTMX for the edit bottom sheet (edit-form GET + edit POST).
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from accounts.services import AccountService
from core.htmx import htmx_redirect
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_none
from virtual_accounts.services import VirtualAccountService

logger = logging.getLogger(__name__)


def _svc(request: AuthenticatedRequest) -> VirtualAccountService:
    """Create a VirtualAccountService for the authenticated user."""
    return VirtualAccountService(request.user_id)


def _parse_positive_float(value: str) -> float | None:
    """Parse a form value as positive float, returning None if zero/negative/invalid."""
    f = parse_float_or_none(value)
    return f if f is not None and f > 0 else None


# ---------------------------------------------------------------------------
# List page
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def virtual_accounts_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /virtual-accounts — list virtual accounts with create form.

    Computes over-allocation warnings when VA balances exceed linked account balances.
    """
    logger.info("page viewed: virtual-accounts, user=%s", request.user_email)
    svc = _svc(request)
    accounts = svc.get_all()
    bank_accounts = AccountService(request.user_id, request.tz).get_for_dropdown(
        include_balance=True
    )

    # Build lookup maps for over-allocation warnings
    account_balances: dict[str, float] = {}
    account_names: dict[str, str] = {}
    for ba in bank_accounts:
        account_balances[ba["id"]] = ba["current_balance"]
        account_names[ba["id"]] = ba["name"]

    # Sum VA balances per linked bank account
    va_group_totals: dict[str, float] = {}
    for va in accounts:
        if va["account_id"]:
            va_group_totals[va["account_id"]] = (
                va_group_totals.get(va["account_id"], 0.0) + va["current_balance"]
            )

    # Generate warning messages for over-allocated account groups
    warnings: list[str] = []
    for acct_id, total_va in va_group_totals.items():
        if acct_id in account_balances and total_va > account_balances[acct_id]:
            warnings.append(
                f"Total virtual account allocations (EGP {total_va:,.2f}) "
                f"exceed {account_names[acct_id]} balance "
                f"(EGP {account_balances[acct_id]:,.2f})"
            )

    # Attach per-VA over-allocation info for template rendering
    for va in accounts:
        va["exceeds_account_balance"] = False
        va["account_balance_display"] = None
        if va["account_id"] and va["account_id"] in account_balances:
            acct_bal = account_balances[va["account_id"]]
            if va["current_balance"] > acct_bal:
                va["exceeds_account_balance"] = True
                va["account_balance_display"] = acct_bal

    return render(
        request,
        "virtual_accounts/virtual_accounts.html",
        {
            "accounts": accounts,
            "bank_accounts": bank_accounts,
            "warnings": warnings,
            "active_tab": "more",
        },
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def virtual_account_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /virtual-accounts/add — create a new virtual account."""
    svc = _svc(request)
    name = request.POST.get("name", "")
    target_amount = _parse_positive_float(request.POST.get("target_amount", ""))
    icon = request.POST.get("icon", "")
    color = request.POST.get("color", "")
    account_id = request.POST.get("account_id", "") or None
    exclude = request.POST.get("exclude_from_net_worth") == "on"

    try:
        svc.create(
            name=name,
            target_amount=target_amount,
            icon=icon,
            color=color,
            account_id=account_id,
            exclude_from_net_worth=exclude,
        )
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return htmx_redirect(request, "/virtual-accounts")


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def virtual_account_detail(request: AuthenticatedRequest, va_id: UUID) -> HttpResponse:
    """GET /virtual-accounts/{id} — detail page with allocations and history.

    Computes over-allocation warnings if VA is linked to a bank account.
    """
    logger.info("page viewed: virtual-account-detail, user=%s", request.user_email)
    svc = _svc(request)
    va = svc.get_by_id(str(va_id))
    if not va:
        return HttpResponse("Virtual account not found", status=404)

    transactions = svc.get_transactions(str(va_id), limit=50)
    allocations = svc.get_allocations(str(va_id), limit=50)

    # Over-allocation warnings for linked bank account
    linked_account: dict[str, Any] | None = None
    over_allocated = False
    account_over_allocated = False
    total_va_balance = 0.0

    if va["account_id"]:
        bank_accounts = AccountService(request.user_id, request.tz).get_for_dropdown(
            include_balance=True
        )
        for ba in bank_accounts:
            if ba["id"] == va["account_id"]:
                linked_account = ba
                break

        if linked_account:
            if va["current_balance"] > linked_account["current_balance"]:
                over_allocated = True

            # Sum all sibling VA balances linked to the same bank account
            sibling_vas = svc.get_by_account_id(va["account_id"])
            for sibling in sibling_vas:
                total_va_balance += sibling["current_balance"]
            if total_va_balance > linked_account["current_balance"]:
                account_over_allocated = True

    return render(
        request,
        "virtual_accounts/virtual_account_detail.html",
        {
            "account": va,
            "transactions": transactions,
            "allocations": allocations,
            "linked_account": linked_account,
            "over_allocated": over_allocated,
            "account_over_allocated": account_over_allocated,
            "total_va_balance": total_va_balance,
            "active_tab": "more",
        },
    )


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def virtual_account_archive(request: AuthenticatedRequest, va_id: UUID) -> HttpResponse:
    """POST /virtual-accounts/{id}/archive — archive (soft-delete) a VA."""
    svc = _svc(request)
    if not svc.archive(str(va_id)):
        logger.warning(
            "virtual account archive failed: not found id=%s user=%s",
            va_id,
            request.user_id,
        )
    return htmx_redirect(request, "/virtual-accounts")


# ---------------------------------------------------------------------------
# Direct allocation
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def virtual_account_allocate(
    request: AuthenticatedRequest, va_id: UUID
) -> HttpResponse:
    """POST /virtual-accounts/{id}/allocate — direct allocation.

    Contribution = positive amount, withdrawal = negative.
    """
    svc = _svc(request)
    amount_str = request.POST.get("amount", "")
    alloc_type = request.POST.get("type", "contribution")
    note = request.POST.get("note", "")

    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        return HttpResponse("Invalid amount", status=400)

    if amount <= 0:
        return HttpResponse("Invalid amount", status=400)

    # Negate for withdrawals
    alloc_amount = -amount if alloc_type == "withdrawal" else amount

    try:
        svc.direct_allocate(
            va_id=str(va_id),
            amount=alloc_amount,
            note=note,
            allocated_at=datetime.now(request.tz),
        )
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return htmx_redirect(request, f"/virtual-accounts/{va_id}")


# ---------------------------------------------------------------------------
# Toggle exclude from net worth
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def virtual_account_toggle_exclude(
    request: AuthenticatedRequest, va_id: UUID
) -> HttpResponse:
    """POST /virtual-accounts/{id}/toggle-exclude — toggle net worth exclusion."""
    svc = _svc(request)
    if not svc.toggle_exclude(str(va_id)):
        return HttpResponse("Virtual account not found", status=404)
    return htmx_redirect(request, f"/virtual-accounts/{va_id}")


# ---------------------------------------------------------------------------
# Edit form (HTMX partial)
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def virtual_account_edit_form(
    request: AuthenticatedRequest, va_id: UUID
) -> HttpResponse:
    """GET /virtual-accounts/{id}/edit-form — edit form partial for bottom sheet.

    Returns an HTML fragment (not a full page) for HTMX to swap into the sheet.
    """
    logger.info(
        "partial loaded: virtual-account-edit-form, user=%s",
        request.user_email,
    )
    svc = _svc(request)
    va = svc.get_by_id(str(va_id))
    if not va:
        return HttpResponse("Virtual account not found", status=404)

    bank_accounts = AccountService(request.user_id, request.tz).get_for_dropdown(
        include_balance=True
    )
    return render(
        request,
        "virtual_accounts/_edit_form.html",
        {"account": va, "bank_accounts": bank_accounts},
    )


# ---------------------------------------------------------------------------
# Update (HTMX form submission)
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def virtual_account_update(request: AuthenticatedRequest, va_id: UUID) -> HttpResponse:
    """POST /virtual-accounts/{id}/edit — update VA from edit bottom sheet.

    Returns error HTML for HTMX swap on validation failure, or redirects on success.
    """
    svc = _svc(request)
    name = request.POST.get("name", "")
    target_amount = _parse_positive_float(request.POST.get("target_amount", ""))
    icon = request.POST.get("icon", "")
    color = request.POST.get("color", "")
    account_id = request.POST.get("account_id", "") or None
    exclude = request.POST.get("exclude_from_net_worth") == "on"

    try:
        updated = svc.update(
            va_id=str(va_id),
            name=name,
            target_amount=target_amount,
            icon=icon,
            color=color,
            account_id=account_id,
            exclude_from_net_worth=exclude,
        )
    except ValueError as e:
        return HttpResponse(
            f'<div class="bg-red-50 dark:bg-red-900/20 text-red-700 '
            f'dark:text-red-400 p-3 rounded-lg text-sm mb-3">{e}</div>',
            status=422,
        )

    if not updated:
        return HttpResponse("Virtual account not found", status=404)

    return htmx_redirect(request, f"/virtual-accounts/{va_id}")


# ---------------------------------------------------------------------------
# Legacy redirects (/virtual-funds → /virtual-accounts)
# ---------------------------------------------------------------------------


@general_rate
def virtual_funds_redirect(request: AuthenticatedRequest) -> HttpResponse:
    """Redirect /virtual-funds to /virtual-accounts (legacy URL support)."""
    return redirect("virtual-accounts", permanent=True)


@general_rate
def virtual_fund_detail_redirect(
    request: AuthenticatedRequest, va_id: UUID
) -> HttpResponse:
    """Redirect /virtual-funds/{id} to /virtual-accounts/{id}."""
    return redirect("va-detail", va_id=va_id, permanent=True)
