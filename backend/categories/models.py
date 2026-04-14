"""Categories models — moved from core.models (Phase 3 migration)."""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now
from django.utils.translation import get_language

from core.managers import UserScopedManager

GEN_UUID = Func(function="gen_random_uuid")


class Category(models.Model):
    """Expense or income category. is_system marks auto-seeded categories."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id"
    )
    name = models.JSONField(default=dict)
    type = models.CharField(max_length=20)
    icon = models.CharField(max_length=10, null=True, blank=True)
    is_system = models.BooleanField(default=False, db_default=False)
    is_archived = models.BooleanField(default=False, db_default=False)
    display_order = models.IntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "categories"

    @staticmethod
    def make_name(*, en: str, ar: str | None = None) -> dict[str, str]:
        """Build a JSONB name dict. Arabic is optional."""
        result: dict[str, str] = {"en": en}
        if ar:
            result["ar"] = ar
        return result

    def get_display_name(self, lang: str | None = None) -> str:
        """Return the category name for the given language.

        Falls back to English if the requested language key is missing.
        Falls back to the first available value if neither key exists.
        """
        if not isinstance(self.name, dict):
            return str(self.name) if self.name else ""
        lang = lang or get_language() or "en"
        lang_code = lang.split("-")[0]
        if lang_code in self.name:
            return str(self.name[lang_code])
        if "en" in self.name:
            return str(self.name["en"])
        if self.name:
            return str(next(iter(self.name.values())))
        return ""

    def __str__(self) -> str:
        return self.get_display_name()
