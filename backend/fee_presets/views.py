"""Fee preset views — settings page and API endpoints for preset management."""

import logging
from decimal import Decimal

from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.ratelimit import general_rate
from core.types import AuthenticatedRequest

from .services import FeePresetService

logger = logging.getLogger(__name__)


def _svc(request: AuthenticatedRequest) -> FeePresetService:
    """Create a FeePresetService scoped to the authenticated user."""
    return FeePresetService(request.user_id)


@general_rate
@require_http_methods(["GET"])
def fee_presets_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /settings/fee-presets - fee preset management page."""
    svc = _svc(request)
    presets = svc.list_all()

    # Group by currency for display
    presets_by_currency: dict[str, dict[str, list[dict]]] = {}
    for p in presets:
        curr = p["currency"]
        if curr not in presets_by_currency:
            presets_by_currency[curr] = {"active": [], "archived": []}
        if p["archived"]:
            presets_by_currency[curr]["archived"].append(p)
        else:
            presets_by_currency[curr]["active"].append(p)

    logger.info("page viewed: fee-presets, user=%s", request.user_email)
    return render(
        request,
        "fee_presets/fee_presets.html",
        {
            "presets_by_currency": presets_by_currency,
            "currencies": sorted(presets_by_currency.keys()),
        },
    )


@general_rate
@require_http_methods(["GET"])
def fee_preset_new_form(request: AuthenticatedRequest) -> HttpResponse:
    """GET /settings/fee-presets/new-form — bottom sheet form partial."""
    from auth_app.currency import get_supported_currencies

    return render(
        request,
        "fee_presets/_fee_preset_new_form.html",
        {
            "supported_currencies": get_supported_currencies(),
        },
    )


@general_rate
@require_http_methods(["POST"])
def fee_preset_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /settings/fee-presets/add — create a new fee preset."""
    svc = _svc(request)

    name = request.POST.get("name", "").strip()
    currency = request.POST.get("currency", "").strip().upper()
    calc_type = request.POST.get("calc_type", "")
    value = request.POST.get("value", "")
    min_fee = request.POST.get("min_fee", "") or None
    max_fee = request.POST.get("max_fee", "") or None

    try:
        svc.create(
            name=name,
            currency=currency,
            calc_type=calc_type,
            value=Decimal(value) if value else Decimal("0"),
            min_fee=Decimal(min_fee) if min_fee else None,
            max_fee=Decimal(max_fee) if max_fee else None,
        )
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return HttpResponseRedirect("/settings/fee-presets")


@general_rate
@require_http_methods(["POST"])
def fee_preset_update(request: AuthenticatedRequest, preset_id: str) -> HttpResponse:
    """POST /settings/fee-presets/<id>/update — edit preset."""
    svc = _svc(request)

    fields: dict[str, object] = {}
    if "name" in request.POST:
        fields["name"] = request.POST.get("name", "").strip()
    if "value" in request.POST:
        fields["value"] = Decimal(request.POST.get("value", "0"))
    if "min_fee" in request.POST:
        min_val = request.POST.get("min_fee", "")
        fields["min_fee"] = Decimal(min_val) if min_val else None
    if "max_fee" in request.POST:
        max_val = request.POST.get("max_fee", "")
        fields["max_fee"] = Decimal(max_val) if max_val else None

    try:
        svc.update(str(preset_id), **fields)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return HttpResponseRedirect("/settings/fee-presets")


@general_rate
@require_http_methods(["POST"])
def fee_preset_archive(request: AuthenticatedRequest, preset_id: str) -> HttpResponse:
    """POST /settings/fee-presets/<id>/archive — archive a preset."""
    svc = _svc(request)
    svc.archive(str(preset_id))
    return HttpResponseRedirect("/settings/fee-presets")


@general_rate
@require_http_methods(["POST"])
def fee_preset_unarchive(request: AuthenticatedRequest, preset_id: str) -> HttpResponse:
    """POST /settings/fee-presets/<id>/unarchive — restore a preset."""
    svc = _svc(request)
    svc.unarchive(str(preset_id))
    return HttpResponseRedirect("/settings/fee-presets")


# ---------------------------------------------------------------------------
# API Endpoints for Transaction Forms
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def api_fee_presets_for_currency(request: AuthenticatedRequest) -> JsonResponse:
    """GET /api/fee-presets?currency=EGP — return active presets for currency."""
    currency = request.GET.get("currency", "")
    svc = _svc(request)
    presets = svc.list_active(currency=currency if currency else None)
    return JsonResponse({"presets": presets})


@general_rate
@require_http_methods(["GET"])
def api_fee_preset_calculate(request: AuthenticatedRequest) -> JsonResponse:
    """GET /api/fee-presets/calculate?preset_id=<id>&amount=<val> — compute fee."""
    preset_id = request.GET.get("preset_id", "")
    amount_str = request.GET.get("amount", "0")

    if not preset_id:
        return JsonResponse({"error": "preset_id required"}, status=400)

    try:
        amount = Decimal(amount_str)
    except Exception:
        return JsonResponse({"error": "invalid amount"}, status=400)

    svc = _svc(request)
    try:
        fee = svc.compute(preset_id, amount)
        return JsonResponse({"fee": str(fee)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
