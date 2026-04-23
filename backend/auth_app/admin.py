from django.contrib import admin

from auth_app.models import (
    AuthToken,
    HistoricalSnapshot,
    Session,
    User,
    UserConfig,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "language", "created_at"]
    search_fields = ["email"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["user", "expires_at", "created_at"]
    list_filter = ["expires_at"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "created_at"


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ["email", "purpose", "used", "expires_at", "created_at"]
    list_filter = ["purpose", "used"]
    search_fields = ["email"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "created_at"


@admin.register(UserConfig)
class UserConfigAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(HistoricalSnapshot)
class HistoricalSnapshotAdmin(admin.ModelAdmin):
    list_display = ["user", "date", "currency", "net_worth", "daily_spending"]
    list_filter = ["date", "currency"]
    search_fields = ["user__email", "currency"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "date"
