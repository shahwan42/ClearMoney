"""
Accounts & Institutions views - all /accounts/* and /institutions/* routes.

Handles pages, HTMX partials, and mutations.
Like Laravel's AccountController - thin views that delegate to services.
"""

import dataclasses
import json
import logging
from typing import Any
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.models import SystemBank
from core.billing import get_credit_card_utilization
from core.htmx import (
    htmx_redirect,
    render_htmx_result,
    success_html,
    validation_error_response,
)
from core.ratelimit import api_rate, general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_none, parse_json_body

from .institution_data import EGYPTIAN_BANKS, EGYPTIAN_FINTECHS, WALLET_EXAMPLES
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


def _render_balance_check_page(
    request: AuthenticatedRequest,
    account_id: str,
    *,
    entered_balance: float | None = None,
    error: str | None = None,
) -> HttpResponse:
    """Render the balance check page with optional entered balance context."""
    svc = AccountService(request.user_id, request.tz)
    account = svc.get_by_id(account_id)
    if not account:
        return HttpResponse("Not found", status=404)

    difference = None
    show_correction = False
    if entered_balance is not None:
        difference = entered_balance - account.current_balance
        show_correction = abs(difference) >= 0.01

    return render(
        request,
        "accounts/balance_check.html",
        {
            "account": account,
            "entered_balance": entered_balance,
            "difference": difference,
            "show_correction": show_correction,
            "error": error,
            "active_tab": "accounts",
        },
    )


# ---------------------------------------------------------------------------
# Page Views
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def accounts_list(request: AuthenticatedRequest) -> HttpResponse:
    """GET /accounts - accounts list grouped by institution."""
    logger.info("page viewed: accounts, user=%s", request.user_email)
    groups = _build_institution_groups(request)
    return render(request, "accounts/accounts.html", {"data": groups})


@general_rate
@require_http_methods(["GET"])
def account_detail(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """GET /accounts/{id} - account detail page."""
    acc_svc = AccountService(request.user_id, request.tz)
    data = acc_svc.get_detail_data(str(id))

    if not data:
        return HttpResponse("Account not found", status=404)

    logger.info("page viewed: account-detail, user=%s", request.user_email)
    return render(request, "accounts/account_detail.html", {"data": data})


@general_rate
@require_http_methods(["GET"])
def reconcile_page(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """Legacy reconciliation URL — redirect to balance check."""
    return redirect("account-balance-check", id=id)


@general_rate
@require_http_methods(["POST"])
def reconcile_submit(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """Legacy reconciliation submit URL — redirect to balance check."""
    return redirect("account-balance-check", id=id)


@general_rate
@require_http_methods(["GET"])
def balance_check_page(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """GET /accounts/<id>/balance-check - account-level balance confirmation."""
    return _render_balance_check_page(request, str(id))


@general_rate
@require_http_methods(["POST"])
def balance_check_submit(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /accounts/<id>/balance-check/submit - save entered balance state."""
    entered_balance = parse_float_or_none(request.POST.get("bank_balance", ""))
    if entered_balance is None:
        return _render_balance_check_page(
            request,
            str(id),
            error="Enter the balance shown by your bank.",
        )

    svc = AccountService(request.user_id, request.tz)
    result = svc.record_balance_check(str(id), entered_balance)
    if result["status"] == "matched":
        return redirect("account-detail", id=id)

    return _render_balance_check_page(
        request,
        str(id),
        entered_balance=entered_balance,
    )


@general_rate
@require_http_methods(["POST"])
def balance_check_correct(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /accounts/<id>/balance-check/correct - add explicit correction."""
    entered_balance = parse_float_or_none(request.POST.get("bank_balance", ""))
    if entered_balance is None:
        return _render_balance_check_page(
            request,
            str(id),
            error="Enter the balance shown by your bank.",
        )

    svc = AccountService(request.user_id, request.tz)
    svc.create_balance_correction(str(id), entered_balance)
    return redirect("account-detail", id=id)


@general_rate
@require_http_methods(["GET"])
def credit_card_statement(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """GET /accounts/{id}/statement - credit card statement page."""
    acc_svc = AccountService(request.user_id, request.tz)
    account = acc_svc.get_by_id(str(id))
    if not account:
        return HttpResponse("Account not found", status=404)

    if not account.is_credit_type:
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
        account.current_balance, account.credit_limit
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
    """GET /accounts/form?institution_id=X - account creation form partial."""
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
    """GET /accounts/{id}/edit-form - account edit form partial."""
    acc_svc = AccountService(request.user_id, request.tz)
    account = acc_svc.get_by_id(str(id))
    if not account:
        return HttpResponse("Account not found", status=404)

    roundup_targets = acc_svc.get_roundup_targets(str(id), account.currency)
    logger.info("partial loaded: account-edit-form, user=%s", request.user_email)
    return render(
        request,
        "accounts/_account_edit_form.html",
        {"account": account, "roundup_targets": roundup_targets},
    )


@general_rate
@require_http_methods(["GET"])
def institution_presets(request: AuthenticatedRequest) -> JsonResponse:
    """GET /accounts/institution-presets?type=bank|fintech|wallet - preset list JSON.

    Returns the static preset entries for the requested institution type.
    Used by the institution form's JS combobox and available as an API.
    """
    inst_type = request.GET.get("type", "")
    presets: list[dict[str, str]] = []
    if inst_type == "bank":
        presets = EGYPTIAN_BANKS
    elif inst_type == "fintech":
        presets = EGYPTIAN_FINTECHS
    elif inst_type == "wallet":
        presets = list(WALLET_EXAMPLES)
    else:
        return JsonResponse({"error": f"unknown type: {inst_type}"}, status=400)

    return JsonResponse(presets, safe=False)


def _system_bank_presets_by_type(
    country: str = "EG",
) -> dict[str, list[dict[str, Any]]]:
    """Group active SystemBanks by bank_type into preset-shaped dicts.

    Returned shape matches the JS combobox preset format (name/value/icon/color)
    with an extra `id` field so the form can submit `system_bank_id`. Used by
    the form partial (embedded JSON) and the `/api/system-banks` JSON endpoint.
    """
    out: dict[str, list[dict[str, Any]]] = {"bank": [], "fintech": [], "wallet": []}
    qs = SystemBank.objects.filter(country=country, is_active=True).order_by(
        "display_order", "short_name"
    )
    for sb in qs:
        bucket = out.setdefault(sb.bank_type, [])
        # Keep `value` empty so existing JS uses preset.name as the displayed text.
        # The icon stored in JSON is the basename so /static/img/institutions/{icon}
        # matches the existing combobox path-prefixing convention.
        icon_basename = sb.svg_path.rsplit("/", 1)[-1] if sb.svg_path else ""
        bucket.append(
            {
                "id": sb.pk,
                "name": sb.get_display_name(),
                "value": sb.short_name,
                "icon": icon_basename,
                "color": sb.brand_color,
                "short_name": sb.short_name,
            }
        )
    return out


@general_rate
@require_http_methods(["GET"])
def institution_form_partial(request: AuthenticatedRequest) -> HttpResponse:
    """GET /accounts/institution-form - institution creation form partial."""
    logger.info("partial loaded: institution-form, user=%s", request.user_email)
    sb_presets = _system_bank_presets_by_type()
    presets_json = json.dumps(
        {
            "bank": sb_presets["bank"] + EGYPTIAN_BANKS,
            "fintech": sb_presets["fintech"] + EGYPTIAN_FINTECHS,
            "wallet": sb_presets["wallet"] + list(WALLET_EXAMPLES),
        }
    )
    return render(
        request,
        "accounts/_institution_form.html",
        {"presets_json": presets_json},
    )


@general_rate
@require_http_methods(["GET"])
def api_system_banks(request: AuthenticatedRequest) -> JsonResponse:
    """GET /api/system-banks?q=&country=EG - JSON list of active SystemBanks.

    Authenticated. Returns banks grouped flat with bilingual name resolved
    for the current locale.
    """
    country = request.GET.get("country", "EG")
    q = request.GET.get("q", "").strip().lower()
    qs = SystemBank.objects.filter(country=country, is_active=True).order_by(
        "display_order", "short_name"
    )
    rows: list[dict[str, Any]] = []
    for sb in qs:
        name = sb.get_display_name()
        if q and q not in name.lower() and q not in sb.short_name.lower():
            continue
        rows.append(
            {
                "id": sb.pk,
                "name": name,
                "short_name": sb.short_name,
                "svg_path": sb.svg_path,
                "brand_color": sb.brand_color,
                "bank_type": sb.bank_type,
            }
        )
    return JsonResponse(rows, safe=False)


@general_rate
@require_http_methods(["GET"])
def account_add_form(request: AuthenticatedRequest) -> HttpResponse:
    """GET /accounts/add-form?institution_id=<optional> - unified add account form."""
    institution_id = request.GET.get("institution_id", "")
    acc_svc = AccountService(request.user_id, request.tz)
    ctx = acc_svc.get_add_form_context(institution_id)

    logger.info("partial loaded: add-account-form, user=%s", request.user_email)
    return render(request, "accounts/_add_account_form.html", ctx)


@general_rate
@require_http_methods(["GET"])
def institution_list_partial(request: AuthenticatedRequest) -> HttpResponse:
    """GET /accounts/list - render institution list partial."""
    logger.info("partial loaded: institution-list, user=%s", request.user_email)
    groups = _build_institution_groups(request)
    return render(request, "accounts/_institution_list.html", {"data": groups})


@general_rate
@require_http_methods(["GET"])
def institution_edit_form(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """GET /institutions/{id}/edit-form - institution edit form partial."""
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
    """GET /institutions/{id}/delete-confirm - delete confirmation partial."""
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
    """GET /accounts/empty - empty response for HTMX auto-dismiss."""
    return HttpResponse("", content_type="text/html; charset=utf-8")


# ---------------------------------------------------------------------------
# Mutations - Institutions
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def institution_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /institutions/add - create institution.

    Returns toast + close script + OOB institution list refresh.
    """
    name = request.POST.get("name", "")
    inst_type = request.POST.get("type", "bank")
    icon = request.POST.get("icon", "") or None
    color = request.POST.get("color", "") or None
    system_bank_id = request.POST.get("system_bank_id", "") or None

    inst_svc = InstitutionService(request.user_id, request.tz)
    try:
        inst_svc.create(
            name,
            inst_type,
            icon=icon,
            color=color,
            system_bank_id=system_bank_id,
        )
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
    """PUT /institutions/{id}/update - update institution.

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
    """DELETE /institutions/{id}/delete - delete institution (cascade).

    Returns toast + close script + OOB list refresh.
    """
    inst_svc = InstitutionService(request.user_id, request.tz)
    try:
        deleted = inst_svc.delete(str(id))
    except ValueError as e:
        return render_htmx_result("error", str(e), "")
    if not deleted:
        return render_htmx_result("error", "Failed to delete institution", "")

    html = success_html("Institution deleted!")
    html += "<script>setTimeout(function(){ closeDeleteSheet(); }, 1000);</script>"
    html += _render_institution_list_oob(request)
    return HttpResponse(html)


@general_rate
@require_http_methods(["POST"])
def institutions_reorder(request: AuthenticatedRequest) -> HttpResponse:
    """POST /institutions/reorder - update display_order."""
    ids = request.POST.getlist("id[]")
    if not ids:
        return HttpResponse("No IDs provided", status=400)

    inst_svc = InstitutionService(request.user_id, request.tz)
    inst_svc.reorder(ids)
    return htmx_redirect(request, "/accounts")


# ---------------------------------------------------------------------------
# Mutations - Accounts
# ---------------------------------------------------------------------------


def _render_add_account_error(
    request: AuthenticatedRequest, error: str, data: dict[str, Any]
) -> HttpResponse:
    """Helper to re-render the add account form with error and sticky values."""
    acc_svc = AccountService(request.user_id, request.tz)
    ctx = acc_svc.get_add_form_context(data.get("institution_id", ""))
    ctx.update(
        {
            "error": error,
            "account_type": data.get("type", "current"),
            "account_currency": data.get("currency", "EGP"),
            "account_name": data.get("name", ""),
            "account_balance": data.get("initial_balance", ""),
            "account_credit_limit": data.get("credit_limit", ""),
        }
    )
    return render(request, "accounts/_add_account_form.html", ctx, status=422)


@general_rate
@require_http_methods(["POST"])
def account_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /accounts/add - create account."""
    inst_id = request.POST.get("institution_id", "")
    inst_svc = InstitutionService(request.user_id, request.tz)

    # Unified flow: resolve institution if no ID provided
    if not inst_id:
        name = request.POST.get("institution_name", "").strip()
        if not name:
            return _render_add_account_error(
                request, "Institution name is required", request.POST
            )
        try:
            inst = inst_svc.get_or_create(
                name,
                request.POST.get("institution_type", "bank"),
                icon=request.POST.get("institution_icon") or None,
                color=request.POST.get("institution_color") or None,
            )
            inst_id = inst["id"]
        except ValueError as e:
            return _render_add_account_error(request, str(e), request.POST)

    data = {
        "institution_id": inst_id,
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
        return _render_add_account_error(request, str(e), data)

    # Success: close sheet + OOB list refresh
    html = "<script>BottomSheet.close('create-sheet');</script>"
    html += _render_institution_list_oob(request)
    return HttpResponse(html)


@general_rate
@require_http_methods(["POST"])
def account_update(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /accounts/{id}/edit - update account fields."""
    roundup_increment_raw = request.POST.get("roundup_increment", "")
    roundup_target_id = (
        request.POST.get("roundup_target_account_id", "").strip() or None
    )
    data = {
        "name": request.POST.get("name", ""),
        "type": request.POST.get("type", "current"),
        "currency": request.POST.get("currency", "EGP"),
        "credit_limit": parse_float_or_none(request.POST.get("credit_limit", "")),
        "roundup_increment": int(roundup_increment_raw)
        if roundup_increment_raw
        else None,
        "roundup_target_account_id": roundup_target_id,
    }

    acc_svc = AccountService(request.user_id, request.tz)
    try:
        updated = acc_svc.update(str(id), data)
    except ValueError as e:
        return validation_error_response(str(e))

    if not updated:
        return HttpResponse("Account not found", status=404)

    return htmx_redirect(request, f"/accounts/{id}")


@general_rate
@require_http_methods(["DELETE", "POST"])
def account_delete(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """DELETE /accounts/{id}/delete - soft-delete (remove) account."""
    acc_svc = AccountService(request.user_id, request.tz)
    try:
        acc_svc.remove(str(id))
    except ObjectDoesNotExist:
        return HttpResponse("Account not found", status=404)
    except ValueError as e:
        return render_htmx_result("error", str(e), "")
    except Exception:
        return render_htmx_result("error", "Failed to delete account", "")

    return htmx_redirect(request, "/accounts")


@general_rate
@require_http_methods(["POST"])
def accounts_reorder(request: AuthenticatedRequest) -> HttpResponse:
    """POST /accounts/reorder - update display_order."""
    ids = request.POST.getlist("id[]")
    if not ids:
        return HttpResponse("No IDs provided", status=400)

    acc_svc = AccountService(request.user_id, request.tz)
    acc_svc.reorder(ids)
    return htmx_redirect(request, "/accounts")


@general_rate
@require_http_methods(["POST"])
def toggle_dormant(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /accounts/{id}/dormant - toggle dormant flag."""
    acc_svc = AccountService(request.user_id, request.tz)
    toggled = acc_svc.toggle_dormant(str(id))
    if not toggled:
        return HttpResponse("Account not found", status=404)
    return htmx_redirect(request, f"/accounts/{id}")


@general_rate
@require_http_methods(["POST"])
def health_update(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /accounts/{id}/health - save health constraints."""
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
# JSON API Views - Institutions
# ---------------------------------------------------------------------------


@csrf_exempt  # JSON API - authenticated via session, called by e2e helpers and JS fetch()
@api_rate
@require_http_methods(["GET", "POST"])
def api_institution_list_create(request: AuthenticatedRequest) -> HttpResponse:
    """GET/POST /api/institutions - list all or create an institution (JSON)."""
    inst_svc = InstitutionService(request.user_id, request.tz)

    if request.method == "GET":
        institutions = inst_svc.get_all()
        for inst in institutions:
            inst["user_id"] = request.user_id
        return JsonResponse(institutions, safe=False)

    # POST - create
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
    """GET/PUT/DELETE /api/institutions/{id} - single institution operations (JSON)."""
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
# JSON API Views - Accounts
# ---------------------------------------------------------------------------


@csrf_exempt  # JSON API - authenticated via session, called by e2e helpers and JS fetch()
@api_rate
@require_http_methods(["GET", "POST"])
def api_account_list_create(request: AuthenticatedRequest) -> HttpResponse:
    """GET/POST /api/accounts - list or create accounts (JSON).

    GET supports ?institution_id= filter.
    """
    acc_svc = AccountService(request.user_id, request.tz)

    if request.method == "GET":
        institution_id = request.GET.get("institution_id", "")
        if institution_id:
            summaries = acc_svc.get_by_institution(institution_id)
        else:
            summaries = acc_svc.get_all()
        accounts = [dataclasses.asdict(acc) for acc in summaries]
        for acc in accounts:
            acc["user_id"] = request.user_id
            acc.pop("is_credit_type", None)
            acc.pop("available_credit", None)
        return JsonResponse(accounts, safe=False)

    # POST - create
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
    """GET/PUT/DELETE /api/accounts/{id} - single account operations (JSON)."""
    acc_svc = AccountService(request.user_id, request.tz)
    aid = str(account_id)

    if request.method == "GET":
        acc = acc_svc.get_by_id(aid)
        if not acc:
            return JsonResponse({"error": "account not found"}, status=404)
        import dataclasses

        acc_dict = dataclasses.asdict(acc)
        acc_dict["user_id"] = request.user_id
        acc_dict.pop("is_credit_type", None)
        acc_dict.pop("available_credit", None)
        return JsonResponse(acc_dict)

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
        import dataclasses

        acc_dict = dataclasses.asdict(acc)
        acc_dict["user_id"] = request.user_id
        acc_dict.pop("is_credit_type", None)
        acc_dict.pop("available_credit", None)
        return JsonResponse(acc_dict)

    # DELETE
    try:
        acc_svc.remove(aid)
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Account not found"}, status=404)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception:
        return JsonResponse({"error": "Failed to delete account"}, status=400)
    return HttpResponse(status=204)
