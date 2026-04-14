from django.contrib import admin

from accounts.models import Account, AccountSnapshot, Institution


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "user", "display_order", "created_at"]
    list_filter = ["type"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "type",
        "currency",
        "current_balance",
        "institution",
        "is_dormant",
    ]
    list_filter = ["type", "currency", "is_dormant"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(AccountSnapshot)
class AccountSnapshotAdmin(admin.ModelAdmin):
    list_display = ["account", "date", "balance"]
    list_filter = ["date"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "date"
