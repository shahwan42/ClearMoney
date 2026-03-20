"""
Accounts & Institutions views — all /accounts/* and /institutions/* routes.

Port of Go's PageHandler methods for accounts (pages.go:455-578, 1421-1596,
2530-2912, 3276-3325). Handles pages, HTMX partials, and mutations.

Like Laravel's AccountController — thin views that delegate to services.
"""

import logging
from typing import Any
from uuid import UUID

from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from core.billing import (
    get_billing_cycle_info,
    get_credit_card_utilization,
    parse_billing_cycle,
)
from core.htmx import htmx_redirect, render_htmx_result, success_html
from core.ratelimit import api_rate, general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_none, parse_json_body

from .services import AccountService, InstitutionService, get_statement_data

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_institution_groups(request: AuthenticatedRequest) -> list[dict[str, Any]]:
    """Fetch all institutions with nested accounts. Used by list page and OOB refresh."""
    inst_svc = InstitutionService(request.user_id, request.tz)
    acc_svc = AccountService(request.user_id, request.tz)
    institutions = inst_svc.get_all()
    groups = []
    for inst in institutions:
        accounts = acc_svc.get_by_institution(inst["id"])
        groups.append({"institution": inst, "accounts": accounts})
    return groups


def _render_institution_list_oob(request: AuthenticatedRequest) -> str:
    """Render the institution list as an OOB swap div. Appended to HTMX responses."""
    groups = _build_institution_groups(request)
    inner_html = render_to_string(
        "accounts/_institution_list.html", {"data": groups}, request
    )
    return f'<div id="institution-list" class="space-y-3" hx-swap-oob="innerHTML">{inner_html}</div>'


# ---------------------------------------------------------------------------
# Page Views
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def accounts_list(request: AuthenticatedRequest) -> HttpResponse:
    """GET /accounts — accounts list grouped by institution.

    Port of Go's PageHandler.Accounts() (pages.go:455).
    """
    logger.info("page viewed: accounts, user=%s", request.user_email)
    groups = _build_institution_groups(request)
    return render(request, "accounts/accounts.html", {"data": groups})


@general_rate
@require_http_methods(["GET"])
def account_detail(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """GET /accounts/{id} — account detail page.

    Port of Go's PageHandler.AccountDetail() (pages.go:1421).
    Most complex view: assembles data from 10+ sources.
    """
    acc_svc = AccountService(request.user_id, request.tz)
    account = acc_svc.get_by_id(str(id))
    if not account:
        return HttpResponse("Account not found", status=404)

    logger.info("page viewed: account-detail, user=%s", request.user_email)

    # Institution name
    inst_svc = InstitutionService(request.user_id, request.tz)
    inst = (
        inst_svc.get_by_id(account["institution_id"])
        if account["institution_id"]
        else None
    )
    institution_name = inst["name"] if inst else ""

    # Billing cycle (credit cards only)
    billing_cycle = None
    if account["is_credit_type"] and account["metadata"]:
        cycle = parse_billing_cycle(account["metadata"])
        if cycle:
            from datetime import date

            billing_cycle = get_billing_cycle_info(cycle[0], cycle[1], date.today())

    # Balance history (30-day sparkline)
    balance_history = acc_svc.get_balance_history(str(id))

    # Credit utilization
    utilization = 0.0
    utilization_history: list[float] = []
    if account["is_credit_type"]:
        utilization = get_credit_card_utilization(
            account["current_balance"], account["credit_limit"]
        )
        if account["credit_limit"] and account["credit_limit"] > 0:
            utilization_history = acc_svc.get_utilization_history(
                str(id), account["credit_limit"]
            )

    # Virtual accounts linked to this account
    virtual_accounts = acc_svc.get_linked_virtual_accounts(str(id))
    excluded_va_balance = acc_svc.get_excluded_va_balance(str(id))

    # Health config
    health_config = account.get("health_config") or {}

    # Recent transactions
    transactions = acc_svc.get_recent_transactions(str(id), limit=50)
    has_more = len(transactions) >= 50

    # Compute "your money" = balance - excluded VA balance
    your_money = account["current_balance"] - excluded_va_balance

    data = {
        "account": account,
        "institution_name": institution_name,
        "billing_cycle": billing_cycle,
        "balance_history": balance_history,
        "utilization": utilization,
        "utilization_history": utilization_history,
        "virtual_accounts": virtual_accounts,
        "excluded_va_balance": excluded_va_balance,
        "your_money": your_money,
        "health_config": health_config,
        "transactions": transactions,
        "has_more": has_more,
    }
    return render(request, "accounts/account_detail.html", {"data": data})


@general_rate
@require_http_methods(["GET"])
def credit_card_statement(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """GET /accounts/{id}/statement — credit card statement page.

    Port of Go's PageHandler.CreditCardStatement() (pages.go:1541).
    """
    acc_svc = AccountService(request.user_id, request.tz)
    account = acc_svc.get_by_id(str(id))
    if not account:
        return HttpResponse("Account not found", status=404)

    if not account["is_credit_type"]:
        return HttpResponse("Not a credit card account", status=400)

    logger.info("page viewed: cc-statement, user=%s", request.user_email)

    period_str = request.GET.get("period", "")
    statement = get_statement_data(account, request.user_id, request.tz, period_str)

    if not statement:
        return render(
            request,
            "accounts/credit_card_statement_error.html",
            {
                "data": {
                    "account": account,
                    "message": "Please configure a billing cycle for this credit card (statement day and due day) in the account metadata.",
                }
            },
        )

    # Utilization for donut chart
    utilization = get_credit_card_utilization(
        account["current_balance"], account["credit_limit"]
    )

    # Utilization color segment for donut
    if utilization > 80:
        util_color = "#ef4444"  # red
    elif utilization > 50:
        util_color = "#f59e0b"  # amber
    else:
        util_color = "#10b981"  # green

    util_segments = [
        {"label": "Used", "percentage": utilization, "color": util_color},
        {"label": "Available", "percentage": 100 - utilization, "color": "#e5e7eb"},
    ]

    data = {
        "statement": statement,
        "utilization": utilization,
        "util_segments": util_segments,
    }
    return render(request, "accounts/credit_card_statement.html", {"data": data})


# ---------------------------------------------------------------------------
# HTMX Partials
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def account_form(request: AuthenticatedRequest) -> HttpResponse:
    """GET /accounts/form?institution_id=X — account creation form partial.

    Port of Go's PageHandler.AccountForm() (pages.go:491).
    """
    institution_id = request.GET.get("institution_id", "")
    if not institution_id:
        return HttpResponse("institution_id required", status=400)

    inst_svc = InstitutionService(request.user_id, request.tz)
    inst = inst_svc.get_by_id(institution_id)
    institution_name = inst["name"] if inst else ""

    logger.info("partial loaded: account-form, user=%s", request.user_email)
    return render(
        request,
        "accounts/_account_form.html",
        {
            "institution_id": institution_id,
            "institution_name": institution_name,
        },
    )


@general_rate
@require_http_methods(["GET"])
def account_edit_form(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """GET /accounts/{id}/edit-form — account edit form partial.

    Port of Go's PageHandler.AccountEditForm() (pages.go:520).
    """
    acc_svc = AccountService(request.user_id, request.tz)
    account = acc_svc.get_by_id(str(id))
    if not account:
        return HttpResponse("Account not found", status=404)

    logger.info("partial loaded: account-edit-form, user=%s", request.user_email)
    return render(request, "accounts/_account_edit_form.html", {"account": account})


@general_rate
@require_http_methods(["GET"])
def institution_form_partial(request: AuthenticatedRequest) -> HttpResponse:
    """GET /accounts/institution-form — institution creation form partial.

    Port of Go's PageHandler.InstitutionFormPartial() (pages.go:2829).
    """
    logger.info("partial loaded: institution-form, user=%s", request.user_email)
    return render(request, "accounts/_institution_form.html", {})


@general_rate
@require_http_methods(["GET"])
def institution_list_partial(request: AuthenticatedRequest) -> HttpResponse:
    """GET /accounts/list — render institution list partial.

    Port of Go's PageHandler.InstitutionList() (pages.go:2772).
    """
    logger.info("partial loaded: institution-list, user=%s", request.user_email)
    groups = _build_institution_groups(request)
    return render(request, "accounts/_institution_list.html", {"data": groups})


@general_rate
@require_http_methods(["GET"])
def institution_edit_form(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """GET /institutions/{id}/edit-form — institution edit form partial.

    Port of Go's PageHandler.InstitutionEditForm() (pages.go:2839).
    """
    inst_svc = InstitutionService(request.user_id, request.tz)
    inst = inst_svc.get_by_id(str(id))
    if not inst:
        return HttpResponse("Institution not found", status=404)

    logger.info("partial loaded: institution-edit-form, user=%s", request.user_email)
    return render(
        request, "accounts/_institution_edit_form.html", {"institution": inst}
    )


@general_rate
@require_http_methods(["GET"])
def institution_delete_confirm(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """GET /institutions/{id}/delete-confirm — delete confirmation partial.

    Port of Go's PageHandler.InstitutionDeleteConfirm() (pages.go:2677).
    """
    inst_svc = InstitutionService(request.user_id, request.tz)
    inst = inst_svc.get_by_id(str(id))
    if not inst:
        return HttpResponse("Institution not found", status=404)

    acc_svc = AccountService(request.user_id, request.tz)
    accounts = acc_svc.get_by_institution(str(id))

    logger.info(
        "partial loaded: institution-delete-confirm, user=%s", request.user_email
    )
    return render(
        request,
        "accounts/_institution_delete_confirm.html",
        {
            "institution_id": str(id),
            "institution_name": inst["name"],
            "account_count": len(accounts),
        },
    )


@general_rate
@require_http_methods(["GET"])
def empty_partial(request: AuthenticatedRequest) -> HttpResponse:
    """GET /accounts/empty — empty response for HTMX auto-dismiss.

    Port of Go's PageHandler.EmptyPartial() (pages.go:2910).
    """
    return HttpResponse("", content_type="text/html; charset=utf-8")


# ---------------------------------------------------------------------------
# Mutations — Institutions
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def institution_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /institutions/add — create institution.

    Port of Go's PageHandler.InstitutionAdd() (pages.go:2646).
    Returns toast + close script + OOB institution list refresh.
    """
    name = request.POST.get("name", "")
    inst_type = request.POST.get("type", "bank")

    inst_svc = InstitutionService(request.user_id, request.tz)
    try:
        inst_svc.create(name, inst_type)
    except ValueError as e:
        return render(
            request,
            "accounts/_institution_form.html",
            {"error": str(e)},
            status=422,
        )

    # Success: toast + close script + OOB list refresh
    html = success_html("Institution added!")
    html += "<script>setTimeout(function(){ closeCreateSheet(); }, 1000);</script>"
    html += _render_institution_list_oob(request)
    return HttpResponse(html)


@general_rate
@require_http_methods(["PUT", "POST"])
def institution_update(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """PUT /institutions/{id}/update — update institution.

    Port of Go's PageHandler.InstitutionUpdate() (pages.go:2861).
    Returns close script + OOB card swap.
    """
    # Django doesn't auto-parse PUT body into request.POST
    data = request.POST if request.method == "POST" else QueryDict(request.body)
    name = data.get("name", "")
    inst_type = data.get("type", "bank")

    inst_svc = InstitutionService(request.user_id, request.tz)
    try:
        updated = inst_svc.update(str(id), name, inst_type)
    except ValueError as e:
        return render(
            request,
            "accounts/_institution_edit_form.html",
            {
                "institution": {"id": str(id), "name": name, "type": inst_type},
                "error": str(e),
            },
            status=422,
        )

    if not updated:
        return HttpResponse("Institution not found", status=404)

    # Fetch accounts to render the updated card
    acc_svc = AccountService(request.user_id, request.tz)
    accounts = acc_svc.get_by_institution(str(id))

    # Close sheet + OOB swap for this specific card
    html = "<script>closeEditSheet();</script>"
    card_html = render_to_string(
        "accounts/_institution_card.html",
        {"institution": updated, "accounts": accounts},
        request,
    )
    html += f'<div id="institution-{id}" hx-swap-oob="outerHTML:#institution-{id}">{card_html}</div>'
    return HttpResponse(html)


@general_rate
@require_http_methods(["DELETE", "POST"])
def institution_delete(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """DELETE /institutions/{id}/delete — delete institution (cascade).

    Port of Go's PageHandler.InstitutionDelete() (pages.go:2703).
    Returns toast + close script + OOB list refresh.
    """
    inst_svc = InstitutionService(request.user_id, request.tz)
    deleted = inst_svc.delete(str(id))
    if not deleted:
        return render_htmx_result("error", "Failed to delete institution", "")

    html = success_html("Institution deleted!")
    html += "<script>setTimeout(function(){ closeDeleteSheet(); }, 1000);</script>"
    html += _render_institution_list_oob(request)
    return HttpResponse(html)


@general_rate
@require_http_methods(["POST"])
def institutions_reorder(request: AuthenticatedRequest) -> HttpResponse:
    """POST /institutions/reorder — update display_order.

    Port of Go's PageHandler.ReorderInstitutions() (pages.go:2558).
    """
    ids = request.POST.getlist("id[]")
    if not ids:
        return HttpResponse("No IDs provided", status=400)

    inst_svc = InstitutionService(request.user_id, request.tz)
    inst_svc.reorder(ids)
    return htmx_redirect(request, "/accounts")


# ---------------------------------------------------------------------------
# Mutations — Accounts
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def account_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /accounts/add — create account.

    Port of Go's PageHandler.AccountAdd() (pages.go:2723).
    Returns close script + OOB institution list refresh.
    """
    institution_id = request.POST.get("institution_id", "")
    institution_name = request.POST.get("institution_name_display", "")

    data = {
        "institution_id": institution_id,
        "name": request.POST.get("name", ""),
        "type": request.POST.get("type", "current"),
        "currency": request.POST.get("currency", "EGP"),
        "initial_balance": parse_float_or_none(request.POST.get("initial_balance", ""))
        or 0.0,
        "credit_limit": parse_float_or_none(request.POST.get("credit_limit", "")),
    }

    acc_svc = AccountService(request.user_id, request.tz)
    try:
        acc_svc.create(data)
    except ValueError as e:
        return render(
            request,
            "accounts/_account_form.html",
            {
                "institution_id": institution_id,
                "institution_name": institution_name,
                "error": str(e),
            },
            status=422,
        )

    # Success: close sheet + OOB list refresh
    html = "<script>closeAccountSheet();</script>"
    html += _render_institution_list_oob(request)
    return HttpResponse(html)


@general_rate
@require_http_methods(["POST"])
def account_update(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /accounts/{id}/edit — update account fields.

    Port of Go's PageHandler.AccountUpdate() (pages.go:541).
    """
    data = {
        "name": request.POST.get("name", ""),
        "type": request.POST.get("type", "current"),
        "currency": request.POST.get("currency", "EGP"),
        "credit_limit": parse_float_or_none(request.POST.get("credit_limit", "")),
    }

    acc_svc = AccountService(request.user_id, request.tz)
    try:
        updated = acc_svc.update(str(id), data)
    except ValueError as e:
        return HttpResponse(
            f'<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm mb-3">{e}</div>',
            status=422,
        )

    if not updated:
        return HttpResponse("Account not found", status=404)

    return htmx_redirect(request, f"/accounts/{id}")


@general_rate
@require_http_methods(["DELETE", "POST"])
def account_delete(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """DELETE /accounts/{id}/delete — delete account.

    Port of Go's PageHandler.AccountDelete() (pages.go:3304).
    Checks for installment FK RESTRICT.
    """
    acc_svc = AccountService(request.user_id, request.tz)
    error = acc_svc.delete(str(id))

    if error:
        if "installment" in error.lower():
            return render_htmx_result(
                "error",
                "Cannot delete: active installment plans exist",
                "Delete or complete the installment plans first, then try again.",
            )
        if "not found" in error.lower():
            return HttpResponse("Account not found", status=404)
        return render_htmx_result("error", "Failed to delete account", "")

    return htmx_redirect(request, "/accounts")


@general_rate
@require_http_methods(["POST"])
def accounts_reorder(request: AuthenticatedRequest) -> HttpResponse:
    """POST /accounts/reorder — update display_order.

    Port of Go's PageHandler.ReorderAccounts() (pages.go:2543).
    """
    ids = request.POST.getlist("id[]")
    if not ids:
        return HttpResponse("No IDs provided", status=400)

    acc_svc = AccountService(request.user_id, request.tz)
    acc_svc.reorder(ids)
    return htmx_redirect(request, "/accounts")


@general_rate
@require_http_methods(["POST"])
def toggle_dormant(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /accounts/{id}/dormant — toggle dormant flag.

    Port of Go's PageHandler.ToggleDormant() (pages.go:2530).
    """
    acc_svc = AccountService(request.user_id, request.tz)
    toggled = acc_svc.toggle_dormant(str(id))
    if not toggled:
        return HttpResponse("Account not found", status=404)
    return htmx_redirect(request, f"/accounts/{id}")


@general_rate
@require_http_methods(["POST"])
def health_update(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /accounts/{id}/health — save health constraints.

    Port of Go's PageHandler.AccountHealthUpdate() (pages.go:3276).
    """
    config: dict[str, float | None] = {}

    min_balance = parse_float_or_none(request.POST.get("min_balance", ""))
    if min_balance is not None and min_balance > 0:
        config["min_balance"] = min_balance
    else:
        config["min_balance"] = None

    min_deposit = parse_float_or_none(request.POST.get("min_monthly_deposit", ""))
    if min_deposit is not None and min_deposit > 0:
        config["min_monthly_deposit"] = min_deposit
    else:
        config["min_monthly_deposit"] = None

    acc_svc = AccountService(request.user_id, request.tz)
    acc_svc.update_health_config(str(id), config)
    return htmx_redirect(request, f"/accounts/{id}")


# ---------------------------------------------------------------------------
# JSON API Views — Institutions (port of Go's InstitutionHandler)
# ---------------------------------------------------------------------------


@api_rate
@require_http_methods(["GET", "POST"])
def api_institution_list_create(request: AuthenticatedRequest) -> HttpResponse:
    """GET/POST /api/institutions — list all or create an institution (JSON)."""
    inst_svc = InstitutionService(request.user_id, request.tz)

    if request.method == "GET":
        institutions = inst_svc.get_all()
        # Add user_id to match Go's JSON output
        for inst in institutions:
            inst["user_id"] = request.user_id
        return JsonResponse(institutions, safe=False)

    # POST — create
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    try:
        inst = inst_svc.create(
            name=body.get("name", ""),
            inst_type=body.get("type", ""),
        )
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    inst["user_id"] = request.user_id
    return JsonResponse(inst, status=201)


@api_rate
@require_http_methods(["GET", "PUT", "DELETE"])
def api_institution_detail(request: AuthenticatedRequest, inst_id: str) -> HttpResponse:
    """GET/PUT/DELETE /api/institutions/{id} — single institution operations (JSON)."""
    inst_svc = InstitutionService(request.user_id, request.tz)
    iid = str(inst_id)

    if request.method == "GET":
        inst = inst_svc.get_by_id(iid)
        if not inst:
            return JsonResponse({"error": "institution not found"}, status=404)
        inst["user_id"] = request.user_id
        return JsonResponse(inst)

    if request.method == "PUT":
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"error": "invalid JSON body"}, status=400)

        try:
            inst = inst_svc.update(
                iid,
                name=body.get("name", ""),
                inst_type=body.get("type", ""),
            )
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        if not inst:
            return JsonResponse({"error": "institution not found"}, status=404)
        inst["user_id"] = request.user_id
        return JsonResponse(inst)

    # DELETE
    deleted = inst_svc.delete(iid)
    if not deleted:
        return JsonResponse({"error": "institution not found"}, status=404)
    return HttpResponse(status=204)


# ---------------------------------------------------------------------------
# JSON API Views — Accounts (port of Go's AccountHandler)
# ---------------------------------------------------------------------------


@api_rate
@require_http_methods(["GET", "POST"])
def api_account_list_create(request: AuthenticatedRequest) -> HttpResponse:
    """GET/POST /api/accounts — list or create accounts (JSON).

    GET supports ?institution_id= filter.
    """
    acc_svc = AccountService(request.user_id, request.tz)

    if request.method == "GET":
        institution_id = request.GET.get("institution_id", "")
        if institution_id:
            accounts = acc_svc.get_by_institution(institution_id)
        else:
            accounts = acc_svc.get_all()
        # Add user_id and strip computed fields for Go parity
        for acc in accounts:
            acc["user_id"] = request.user_id
            acc.pop("is_credit_type", None)
            acc.pop("available_credit", None)
        return JsonResponse(accounts, safe=False)

    # POST — create
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    try:
        acc = acc_svc.create(body)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    acc["user_id"] = request.user_id
    acc.pop("is_credit_type", None)
    acc.pop("available_credit", None)
    return JsonResponse(acc, status=201)


@api_rate
@require_http_methods(["GET", "PUT", "DELETE"])
def api_account_detail(request: AuthenticatedRequest, account_id: str) -> HttpResponse:
    """GET/PUT/DELETE /api/accounts/{id} — single account operations (JSON)."""
    acc_svc = AccountService(request.user_id, request.tz)
    aid = str(account_id)

    if request.method == "GET":
        acc = acc_svc.get_by_id(aid)
        if not acc:
            return JsonResponse({"error": "account not found"}, status=404)
        acc["user_id"] = request.user_id
        acc.pop("is_credit_type", None)
        acc.pop("available_credit", None)
        return JsonResponse(acc)

    if request.method == "PUT":
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"error": "invalid JSON body"}, status=400)

        try:
            acc = acc_svc.update(aid, body)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        if not acc:
            return JsonResponse({"error": "account not found"}, status=404)
        acc["user_id"] = request.user_id
        acc.pop("is_credit_type", None)
        acc.pop("available_credit", None)
        return JsonResponse(acc)

    # DELETE
    error = acc_svc.delete(aid)
    if error:
        return JsonResponse({"error": error}, status=400)
    return HttpResponse(status=204)
