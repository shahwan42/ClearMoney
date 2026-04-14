from django.contrib import admin

from transactions.models import Transaction, VirtualAccountAllocation


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["date", "type", "amount", "currency", "account", "category", "note"]
    list_filter = ["type", "currency", "date"]
    search_fields = ["note"]
    readonly_fields = ["id", "balance_delta", "created_at", "updated_at"]
    date_hierarchy = "date"


@admin.register(VirtualAccountAllocation)
class VirtualAccountAllocationAdmin(admin.ModelAdmin):
    list_display = ["virtual_account", "amount", "transaction", "allocated_at"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "allocated_at"
