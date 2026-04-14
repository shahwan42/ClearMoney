from django.contrib import admin

from budgets.models import Budget, TotalBudget


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["user", "category", "monthly_limit", "currency", "is_active"]
    list_filter = ["currency", "is_active"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(TotalBudget)
class TotalBudgetAdmin(admin.ModelAdmin):
    list_display = ["user", "monthly_limit", "currency", "is_active"]
    list_filter = ["currency", "is_active"]
    readonly_fields = ["id", "created_at", "updated_at"]
