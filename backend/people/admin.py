from django.contrib import admin

from people.models import Person, PersonCurrencyBalance


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "net_balance", "net_balance_egp", "net_balance_usd"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(PersonCurrencyBalance)
class PersonCurrencyBalanceAdmin(admin.ModelAdmin):
    list_display = ["person", "currency", "balance", "updated_at"]
    list_select_related = ["person", "currency"]
    search_fields = ["person__name", "currency__code"]
    readonly_fields = ["id", "created_at", "updated_at"]
