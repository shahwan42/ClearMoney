"""
People views — page handlers for /people/* and JSON API for /api/persons/*.

Port of Go's PageHandler people methods (pages.go:1220–1408) and
PersonHandler JSON API (person.go).

Like Laravel's PersonController — handles both HTML (HTMX) and JSON endpoints.
"""

import json
import logging
from typing import Any

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from core.types import AuthenticatedRequest
from people.services import PersonService

logger = logging.getLogger(__name__)


def _svc(request: AuthenticatedRequest) -> PersonService:
    """Create a PersonService for the authenticated user."""
    return PersonService(request.user_id, request.tz)


def _parse_float(value: Any) -> float | None:
    """Parse a value to float, returning None if empty or invalid."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _error_html(message: str) -> str:
    """Return styled error HTML for HTMX swap."""
    return f'<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">{message}</div>'


def _get_accounts(request: AuthenticatedRequest) -> list[dict[str, Any]]:
    """Fetch all accounts for the user (for form dropdowns)."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, name, currency, current_balance
               FROM accounts WHERE user_id = %s AND is_dormant = false
               ORDER BY display_order, name""",
            [request.user_id],
        )
        return [
            {
                "id": str(row[0]),
                "name": row[1],
                "currency": row[2],
                "current_balance": float(row[3]),
            }
            for row in cursor.fetchall()
        ]


# ---------------------------------------------------------------------------
# Helper — render people list partial (shared by add/loan/repay)
# ---------------------------------------------------------------------------


def _render_people_list(request: AuthenticatedRequest) -> HttpResponse:
    """Re-render the people list for HTMX innerHTML swap.

    Port of Go's renderPeopleList helper (pages.go:1335–1355).
    """
    svc = _svc(request)
    persons = svc.get_all()
    accounts = _get_accounts(request)

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


@require_http_methods(["GET"])
def people_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /people — people list page with add form.

    Port of Go's PageHandler.People (pages.go:1220–1235).
    """
    logger.info("page viewed: people, user=%s", request.user_email)
    svc = _svc(request)
    persons = svc.get_all()
    accounts = _get_accounts(request)

    cards = [{"person": p, "accounts": accounts} for p in persons]

    return render(
        request,
        "people/people.html",
        {
            "active_tab": "more",
            "data": {"persons": cards, "accounts": accounts},
        },
    )


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

    accounts = _get_accounts(request)

    return render(
        request,
        "people/person_detail.html",
        {
            "active_tab": "more",
            "data": {"summary": summary, "accounts": accounts},
        },
    )


@require_http_methods(["POST"])
def people_loan(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """POST /people/{id}/loan — record loan via HTMX form.

    Port of Go's PageHandler.PeopleLoan (pages.go:1263–1295).
    """
    svc = _svc(request)
    amount = _parse_float(request.POST.get("amount"))
    account_id = request.POST.get("account_id", "")
    loan_type = request.POST.get("loan_type", "loan_out")
    note = request.POST.get("note", "").strip() or None

    if not amount or amount <= 0:
        return HttpResponse(
            _error_html("Amount is required"), status=400, content_type="text/html"
        )

    try:
        svc.record_loan(
            person_id=str(person_id),
            account_id=account_id,
            amount=amount,
            loan_type=loan_type,
            note=note,
        )
    except ValueError as e:
        return HttpResponse(_error_html(str(e)), status=400, content_type="text/html")

    return _render_people_list(request)


@require_http_methods(["POST"])
def people_repay(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """POST /people/{id}/repay — record repayment via HTMX form.

    Port of Go's PageHandler.PeopleRepay (pages.go:1299–1329).
    """
    svc = _svc(request)
    amount = _parse_float(request.POST.get("amount"))
    account_id = request.POST.get("account_id", "")
    note = request.POST.get("note", "").strip() or None

    if not amount or amount <= 0:
        return HttpResponse(
            _error_html("Amount is required"), status=400, content_type="text/html"
        )

    try:
        svc.record_repayment(
            person_id=str(person_id),
            account_id=account_id,
            amount=amount,
            note=note,
        )
    except ValueError as e:
        return HttpResponse(_error_html(str(e)), status=400, content_type="text/html")

    return _render_people_list(request)


# ---------------------------------------------------------------------------
# JSON API Views (port of Go's PersonHandler in person.go)
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def api_person_list_create(request: AuthenticatedRequest) -> HttpResponse:
    """GET/POST /api/persons — list all or create a person (JSON)."""
    svc = _svc(request)

    if request.method == "GET":
        persons = svc.get_all()
        return JsonResponse(persons, safe=False)

    # POST — create
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = body.get("name", "")
    try:
        person = svc.create(name)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(person, status=201)


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
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
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


@require_http_methods(["POST"])
def api_person_loan(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """POST /api/persons/{id}/loan — record loan (JSON).

    Port of Go's PersonHandler.RecordLoan (person.go:148–162).
    """
    svc = _svc(request)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
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


@require_http_methods(["POST"])
def api_person_repayment(request: AuthenticatedRequest, person_id: str) -> HttpResponse:
    """POST /api/persons/{id}/repayment — record repayment (JSON).

    Port of Go's PersonHandler.RecordRepayment (person.go:173–187).
    """
    svc = _svc(request)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
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
