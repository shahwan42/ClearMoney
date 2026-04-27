"""
Category JSON API views — CRUD for expense/income categories.

Like Laravel's CategoryController — handles /api/categories/* JSON endpoints.

No HTML views — categories are only accessed via JSON API (used by HTMX
and potentially mobile clients).
"""

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from categories.services import CategoryService
from core.decorators import inject_service
from core.ratelimit import api_rate
from core.types import AuthenticatedRequest
from core.utils import parse_json_body


@inject_service(CategoryService)
@api_rate
@require_http_methods(["GET", "POST"])
def api_category_list_create(
    request: AuthenticatedRequest, svc: CategoryService
) -> HttpResponse:
    """GET/POST /api/categories — list all or create a category (JSON).

    GET supports ?type=expense|income filter.
    """

    if request.method == "GET":
        cat_type = request.GET.get("type", "")
        if cat_type:
            categories = svc.get_by_type(cat_type)
        else:
            categories = svc.get_all()
        return JsonResponse(categories, safe=False)

    # POST — create
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        category = svc.create(
            name=body.get("name", ""),
            cat_type=body.get("type", "expense"),
            icon=body.get("icon"),
            name_en=body.get("name_en", ""),
            name_ar=body.get("name_ar", ""),
        )
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(category, status=201)


@inject_service(CategoryService)
@api_rate
@require_http_methods(["PUT", "DELETE"])
def api_category_detail(
    request: AuthenticatedRequest, svc: CategoryService, category_id: str
) -> HttpResponse:
    """PUT/DELETE /api/categories/{id} — update or archive a category (JSON).

    PUT updates name and icon. DELETE soft-deletes (archives).
    System categories cannot be modified or archived.
    """
    cid = str(category_id)

    if request.method == "PUT":
        body = parse_json_body(request)
        if body is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        try:
            category = svc.update(
                cid,
                name=body.get("name", ""),
                icon=body.get("icon"),
                name_en=body.get("name_en", ""),
                name_ar=body.get("name_ar", ""),
            )
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
