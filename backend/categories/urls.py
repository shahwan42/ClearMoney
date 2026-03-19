"""
Category URL patterns — JSON API only (no page routes).
"""

from django.urls import path

from categories import views

urlpatterns = [
    path("api/categories", views.api_category_list_create, name="api-categories"),
    path(
        "api/categories/<uuid:category_id>",
        views.api_category_detail,
        name="api-category-detail",
    ),
]
