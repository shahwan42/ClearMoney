from django.contrib import admin

from categories.models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "icon", "is_system", "is_archived", "display_order"]
    list_filter = ["type", "is_system", "is_archived"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]
