from django.contrib import admin

from virtual_accounts.models import VirtualAccount


@admin.register(VirtualAccount)
class VirtualAccountAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "target_amount", "current_balance", "is_archived"]
    list_filter = ["is_archived"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]
