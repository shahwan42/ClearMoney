from django.contrib import admin

from investments.models import Investment


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = [
        "platform",
        "fund_name",
        "units",
        "last_unit_price",
        "currency",
        "user",
    ]
    list_filter = ["currency", "platform"]
    search_fields = ["fund_name", "platform"]
    readonly_fields = ["id", "last_updated", "created_at", "updated_at"]
