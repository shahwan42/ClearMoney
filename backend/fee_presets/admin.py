"""Admin registration for fee presets (read-only / minimal)."""

from django.contrib import admin

from .models import FeePreset


@admin.register(FeePreset)
class FeePresetAdmin(admin.ModelAdmin):
    list_display = ("name", "currency", "calc_type", "value", "user", "archived")
    list_filter = ("currency", "calc_type", "archived")
    search_fields = ("name", "user__email")
