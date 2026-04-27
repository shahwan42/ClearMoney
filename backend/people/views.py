"""
People views — page handlers for /people/* and JSON API for /api/persons/*.

Like Laravel's PersonController — handles both HTML (HTMX) and JSON endpoints.
"""

import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from accounts.services import AccountService
from auth_app.currency import get_user_active_currencies
from core.decorators import inject_service
from core.htmx import error_response
from core.ratelimit import api_rate, general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_none, parse_json_body
from people.services import PersonService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper — render people list partial (shared by add/loan/repay)
# ---------------------------------------------------------------------------


@inject_service(PersonService)
def _render_people_list(
    request: AuthenticatedRequest, svc: PersonService
) -> HttpResponse:
    """Re-render the people list for HTMX innerHTML swap."""
    persons = svc.get_all()
    accounts = AccountService(request.user_id, request.tz).get_for_dropdown(
        include_balance=True
    )
    currencies = get_user_active_currencies(request.user_id)

    if not persons:
        return HttpResponse(
            '<div class="bg-white rounded-xl shadow-sm p-6 text-center">'
            '<p class="text-gray-400 text-sm">No people yet. Add someone above.</p>'
            "</div>"
        )

    html_parts: list[str] = []
    for person in persons:
        html_parts.append(
            render_to_string(
                "people/_person_card.html",
                {"person": person, "accounts": accounts, "currencies": currencies},
                request=request,
            )
        )
    return HttpResponse("".join(html_parts))


# ---------------------------------------------------------------------------
# Page Views (HTML)
# ---------------------------------------------------------------------------


@inject_service(PersonService)
@general_rate
@require_http_methods(["GET"])
def people_page(request: AuthenticatedRequest, svc: PersonService) -> HttpResponse:
    """GET /people — people list page with add form."""
    logger.info("page viewed: people, user=%s", request.user_email)
    persons = svc.get_all()
    accounts = AccountService(request.user_id, request.tz).get_for_dropdown(
        include_balance=True
    )
    currencies = get_user_active_currencies(request.user_id)

    cards = [
        {"person": p, "accounts": accounts, "currencies": currencies} for p in persons
    ]

    return render(
        request,
        "people/people.html",
        {
            "active_tab": "more",
            "data": {"persons": cards, "accounts": accounts},
        },
    )


@inject_service(PersonService)
@general_rate
@require_http_methods(["POST"])
def people_add(request: AuthenticatedRequest, svc: PersonService) -> HttpResponse:
    """POST /people/add — create person via HTMX form."""
    name = request.POST.get("name", "").strip()
    if not name:
        return HttpResponse("name is required", status=400)

    try:
        svc.create(name)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return _render_people_list(request)


@inject_service(PersonService)
@general_rate
@require_http_methods(["GET"])
def person_detail(
    request: AuthenticatedRequest, svc: PersonService, person_id: str
) -> HttpResponse:
    """GET /people/{id} — person detail page with debt summary."""
    logger.info("page viewed: person-detail, user=%s", request.user_email)
    summary = svc.get_debt_summary(str(person_id))
    if not summary:
        return HttpResponse("person not found", status=404)

    accounts = AccountService(request.user_id, request.tz).get_for_dropdown(
        include_balance=True
    )
    currencies = get_user_active_currencies(request.user_id)

    return render(
        request,
        "people/person_detail.html",
        {
            "active_tab": "more",
            "data": {
                "summary": summary,
                "accounts": accounts,
                "currencies": currencies,
            },
        },
    )


@inject_service(PersonService)
@general_rate
@require_http_methods(["POST"])
def people_loan(
    request: AuthenticatedRequest, svc: PersonService, person_id: str
) -> HttpResponse:
    """POST /people/{id}/loan — record loan via HTMX form."""
    amount = parse_float_or_none(request.POST.get("amount"))
    loan_type = request.POST.get("loan_type", "loan_out")
    note = request.POST.get("note", "").strip() or None
    no_account = request.POST.get("no_account") == "1"

    if not amount or amount <= 0:
        return error_response("Amount is required", field="amount")

    account_id: str | None = None
    currency: str | None = None

    if no_account:
        currency = request.POST.get("currency", "").strip() or None
        if not currency:
            return error_response("Currency is required", field="currency")
    else:
        account_id = request.POST.get("account_id", "").strip() or None
        if not account_id:
            return error_response("Account is required", field="account_id")

    try:
        svc.record_loan(
            person_id=str(person_id),
            account_id=account_id,
            amount=amount,
            loan_type=loan_type,
            currency=currency,
            note=note,
        )
    except ValueError as e:
        return error_response(str(e))

    return _render_people_list(request)


@inject_service(PersonService)
@general_rate
@require_http_methods(["POST"])
def people_repay(
    request: AuthenticatedRequest, svc: PersonService, person_id: str
) -> HttpResponse:
    """POST /people/{id}/repay — record repayment via HTMX form."""
    amount = parse_float_or_none(request.POST.get("amount"))
    note = request.POST.get("note", "").strip() or None
    fee_amount = parse_float_or_none(request.POST.get("fee_amount", ""))
    no_account = request.POST.get("no_account") == "1"

    if not amount or amount <= 0:
        return error_response("Amount is required", field="amount")

    account_id: str | None = None
    currency: str | None = None

    if no_account:
        currency = request.POST.get("currency", "").strip() or None
        if not currency:
            return error_response("Currency is required", field="currency")
    else:
        account_id = request.POST.get("account_id", "").strip() or None
        if not account_id:
            return error_response("Account is required", field="account_id")

    try:
        svc.record_repayment(
            person_id=str(person_id),
            account_id=account_id,
            amount=amount,
            currency=currency,
            note=note,
            fee_amount=fee_amount if fee_amount and fee_amount > 0 else None,
        )
    except ValueError as e:
        return error_response(str(e))

    return _render_people_list(request)


# ---------------------------------------------------------------------------
# JSON API Views
# ---------------------------------------------------------------------------


@inject_service(PersonService)
@api_rate
@require_http_methods(["GET", "POST"])
def api_person_list_create(
    request: AuthenticatedRequest, svc: PersonService
) -> HttpResponse:
    """GET/POST /api/persons — list all or create a person (JSON)."""

    if request.method == "GET":
        persons = svc.get_all()
        return JsonResponse(persons, safe=False)

    # POST — create
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = body.get("name", "")
    try:
        person = svc.create(name)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(person, status=201)


@inject_service(PersonService)
@api_rate
@require_http_methods(["GET", "PUT", "DELETE"])
def api_person_detail(
    request: AuthenticatedRequest, svc: PersonService, person_id: str
) -> HttpResponse:
    """GET/PUT/DELETE /api/persons/{id} — single person operations (JSON)."""
    pid = str(person_id)

    if request.method == "GET":
        person = svc.get_by_id(pid)
        if not person:
            return JsonResponse({"error": "person not found"}, status=404)
        return JsonResponse(person)

    if request.method == "PUT":
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        name = body.get("name", "")
        note = body.get("note")
        try:
            person = svc.update(pid, name, note)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        if not person:
            return JsonResponse({"error": "person not found"}, status=404)
        return JsonResponse(person)

    # DELETE
    deleted = svc.delete(pid)
    if not deleted:
        return JsonResponse({"error": "person not found"}, status=404)
    return HttpResponse(status=204)


@inject_service(PersonService)
@api_rate
@require_http_methods(["POST"])
def api_person_loan(
    request: AuthenticatedRequest, svc: PersonService, person_id: str
) -> HttpResponse:
    """POST /api/persons/{id}/loan — record loan (JSON)."""
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        tx = svc.record_loan(
            person_id=str(person_id),
            account_id=body.get("account_id", ""),
            amount=float(body.get("amount", 0)),
            loan_type=body.get("type", ""),
            note=body.get("note"),
        )
    except (ValueError, TypeError) as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(tx, status=201)


@inject_service(PersonService)
@api_rate
@require_http_methods(["POST"])
def api_person_repayment(
    request: AuthenticatedRequest, svc: PersonService, person_id: str
) -> HttpResponse:
    """POST /api/persons/{id}/repayment — record repayment (JSON)."""
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    fee_raw = body.get("fee_amount")
    fee_amount = float(fee_raw) if fee_raw else None

    try:
        tx = svc.record_repayment(
            person_id=str(person_id),
            account_id=body.get("account_id", ""),
            amount=float(body.get("amount", 0)),
            note=body.get("note"),
            fee_amount=fee_amount if fee_amount and fee_amount > 0 else None,
        )
    except (ValueError, TypeError) as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(tx, status=201)
