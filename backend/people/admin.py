from django.contrib import admin

from people.models import Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "net_balance_egp", "net_balance_usd"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]
