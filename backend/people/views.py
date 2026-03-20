"""
People views — page handlers for /people/* and JSON API for /api/persons/*.

Port of Go's PageHandler people methods (pages.go:1220–1408) and
PersonHandler JSON API (person.go).

Like Laravel's PersonController — handles both HTML (HTMX) and JSON endpoints.
"""

import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from accounts.services import AccountService
from core.htmx import error_response
from core.ratelimit import api_rate, general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_none, parse_json_body
from people.services import PersonService

logger = logging.getLogger(__name__)


def _svc(request: AuthenticatedRequest) -> PersonService:
    """Create a PersonService for the authenticated user."""
    return PersonService(request.user_id, request.tz)


# ---------------------------------------------------------------------------
# Helper — render people list partial (shared by add/loan/repay)
# ---------------------------------------------------------------------------


def _render_people_list(request: AuthenticatedRequest) -> HttpResponse:
    """Re-render the people list for HTMX innerHTML swap.

    Port of Go's renderPeopleList helper (pages.go:1335–1355).
    """
    svc = _svc(request)
    persons = svc.get_all()
    accounts = AccountService(request.user_id, request.tz).get_for_dropdown(
        include_balance=True
    )

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
                {"person": person, "accounts": accounts},
                request=request,
            )
        )
    return HttpResponse("".join(html_parts))


# ---------------------------------------------------------------------------
# Page Views (HTML)
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def people_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /people — people list page with add form.

    Port of Go's PageHandler.People (pages.go:1220–1235).
    """
    logger.info("page viewed: people, user=%s", request.user_email)
    svc = _svc(request)
    persons = svc.get_all()
    accounts = AccountService(request.user_id, request.tz).get_for_dropdown(
        include_balance=True
    )

    cards = [{"person": p, "accounts": accounts} for p in persons]

    return render(
        request,
        "people/people.html",
        {
            "active_tab": "more",
            "data": {"persons": cards, "accounts": accounts},
        },
    )


@general_rate
@require_http_methods(["POST"])
def people_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /people/add — create person via HTMX form.

    Port of Go's PageHandler.PeopleAdd (pages.go:1239–1259).
    """
    svc = _svc(request)
    name = request.POST.get("name", "").strip()
    if not name:
        return HttpResponse("name is required", status=400)

    try:
        svc.create(name)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return _render_people_list(request)


@general_rate
@require_http_methods(["GET"])
def person_detail(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """GET /people/{id} — person detail page with debt summary.

    Port of Go's PageHandler.PersonDetail (pages.go:1391–1408).
    """
    logger.info("page viewed: person-detail, user=%s", request.user_email)
    svc = _svc(request)
    summary = svc.get_debt_summary(str(person_id))
    if not summary:
        return HttpResponse("person not found", status=404)

    accounts = AccountService(request.user_id, request.tz).get_for_dropdown(
        include_balance=True
    )

    return render(
        request,
        "people/person_detail.html",
        {
            "active_tab": "more",
            "data": {"summary": summary, "accounts": accounts},
        },
    )


@general_rate
@require_http_methods(["POST"])
def people_loan(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """POST /people/{id}/loan — record loan via HTMX form.

    Port of Go's PageHandler.PeopleLoan (pages.go:1263–1295).
    """
    svc = _svc(request)
    amount = parse_float_or_none(request.POST.get("amount"))
    account_id = request.POST.get("account_id", "")
    loan_type = request.POST.get("loan_type", "loan_out")
    note = request.POST.get("note", "").strip() or None

    if not amount or amount <= 0:
        return error_response("Amount is required")

    try:
        svc.record_loan(
            person_id=str(person_id),
            account_id=account_id,
            amount=amount,
            loan_type=loan_type,
            note=note,
        )
    except ValueError as e:
        return error_response(str(e))

    return _render_people_list(request)


@general_rate
@require_http_methods(["POST"])
def people_repay(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """POST /people/{id}/repay — record repayment via HTMX form.

    Port of Go's PageHandler.PeopleRepay (pages.go:1299–1329).
    """
    svc = _svc(request)
    amount = parse_float_or_none(request.POST.get("amount"))
    account_id = request.POST.get("account_id", "")
    note = request.POST.get("note", "").strip() or None

    if not amount or amount <= 0:
        return error_response("Amount is required")

    try:
        svc.record_repayment(
            person_id=str(person_id),
            account_id=account_id,
            amount=amount,
            note=note,
        )
    except ValueError as e:
        return error_response(str(e))

    return _render_people_list(request)


# ---------------------------------------------------------------------------
# JSON API Views (port of Go's PersonHandler in person.go)
# ---------------------------------------------------------------------------


@api_rate
@require_http_methods(["GET", "POST"])
def api_person_list_create(request: AuthenticatedRequest) -> HttpResponse:
    """GET/POST /api/persons — list all or create a person (JSON)."""
    svc = _svc(request)

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


@api_rate
@require_http_methods(["GET", "PUT", "DELETE"])
def api_person_detail(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """GET/PUT/DELETE /api/persons/{id} — single person operations (JSON)."""
    svc = _svc(request)
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


@api_rate
@require_http_methods(["POST"])
def api_person_loan(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """POST /api/persons/{id}/loan — record loan (JSON).

    Port of Go's PersonHandler.RecordLoan (person.go:148–162).
    """
    svc = _svc(request)
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


@api_rate
@require_http_methods(["POST"])
def api_person_repayment(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """POST /api/persons/{id}/repayment — record repayment (JSON).

    Port of Go's PersonHandler.RecordRepayment (person.go:173–187).
    """
    svc = _svc(request)
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        tx = svc.record_repayment(
            person_id=str(person_id),
            account_id=body.get("account_id", ""),
            amount=float(body.get("amount", 0)),
            note=body.get("note"),
        )
    except (ValueError, TypeError) as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(tx, status=201)
