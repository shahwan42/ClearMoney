from django.contrib import admin

from exchange_rates.models import ExchangeRateLog


@admin.register(ExchangeRateLog)
class ExchangeRateLogAdmin(admin.ModelAdmin):
    list_display = ["date", "rate", "source", "note"]
    list_filter = ["source"]
    search_fields = ["source", "note"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "date"
