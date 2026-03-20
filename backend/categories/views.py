"""
Category JSON API views — CRUD for expense/income categories.

Port of Go's CategoryHandler (handler/category.go).
Like Laravel's CategoryController — handles /api/categories/* JSON endpoints.

No HTML views — categories are only accessed via JSON API (used by HTMX
and potentially mobile clients).
"""

import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from categories.services import CategoryService
from core.types import AuthenticatedRequest


def _svc(request: AuthenticatedRequest) -> CategoryService:
    """Create a CategoryService scoped to the authenticated user."""
    return CategoryService(request.user_id, request.tz)


@require_http_methods(["GET", "POST"])
def api_category_list_create(request: AuthenticatedRequest) -> HttpResponse:
    """GET/POST /api/categories — list all or create a category (JSON).

    GET supports ?type=expense|income filter.
    """
    svc = _svc(request)

    if request.method == "GET":
        cat_type = request.GET.get("type", "")
        if cat_type:
            categories = svc.get_by_type(cat_type)
        else:
            categories = svc.get_all()
        return JsonResponse(categories, safe=False)

    # POST — create
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        category = svc.create(
            name=body.get("name", ""),
            cat_type=body.get("type", ""),
            icon=body.get("icon"),
        )
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(category, status=201)


@require_http_methods(["PUT", "DELETE"])
def api_category_detail(
    request: AuthenticatedRequest, category_id: str
) -> HttpResponse:
    """PUT/DELETE /api/categories/{id} — update or archive a category (JSON).

    PUT updates name and icon. DELETE soft-deletes (archives).
    System categories cannot be modified or archived.
    """
    svc = _svc(request)
    cid = str(category_id)

    if request.method == "PUT":
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        try:
            category = svc.update(cid, name=body.get("name", ""), icon=body.get("icon"))
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        if not category:
            return JsonResponse({"error": "category not found"}, status=404)
        return JsonResponse(category)

    # DELETE — archive (soft delete)
    try:
        svc.archive(cid)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return HttpResponse(status=204)
