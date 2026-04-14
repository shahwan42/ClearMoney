from django.contrib import admin

from recurring.models import RecurringRule


@admin.register(RecurringRule)
class RecurringRuleAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "frequency",
        "day_of_month",
        "next_due_date",
        "is_active",
        "auto_confirm",
    ]
    list_filter = ["frequency", "is_active"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "next_due_date"
