---
id: "507"
title: "SystemBank model + migration"
type: feature
priority: high
status: pending
created: 2026-04-27
updated: 2026-04-27
---

## Description

Create a `SystemBank` DB table that stores curated, admin-managed bank records. Users can link their institutions to a system bank (FK), enabling consistent branding, bilingual names, and official SVG logos across all user accounts.

This is the foundation for Phase 1 localization — all subsequent institution combobox work depends on this model existing.

## Model Fields

```python
class SystemBank(models.Model):
    class Meta:
        db_table = "system_banks"

    name = models.JSONField()           # {"en": "CIB", "ar": "البنك التجاري الدولي"}
    short_name = models.CharField(max_length=20)  # "CIB" — used in fallback SVG
    svg_path = models.CharField(max_length=200, blank=True)  # "banks/cib.svg" — relative to STATIC_ROOT
    brand_color = models.CharField(max_length=7, blank=True)  # "#003366" — hex for fallback SVG bg
    country = models.CharField(max_length=2, default="EG")  # ISO 3166-1 alpha-2
    bank_type = models.CharField(max_length=20, choices=[("bank","Bank"),("fintech","Fintech"),("wallet","Wallet")], default="bank")
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    def get_display_name(self, lang: str | None = None) -> str:
        # same pattern as Category.get_display_name()
        ...
```

## Acceptance Criteria

- [ ] `SystemBank` model created in `core/models.py` with all fields above
- [ ] Migration generated and applied cleanly
- [ ] `get_display_name(lang)` method follows same pattern as `Category.get_display_name()`
- [ ] `django.contrib.admin` registered for `SystemBank` (for future admin management)
- [ ] `mcp__django-ai-boost__run_check` passes
- [ ] Unit tests: model creation, `get_display_name` with en/ar/None/missing-key cases
- [ ] `make test && make lint` both pass

## Dependencies

None — this is the base ticket for Phase 1.

## Progress Notes

- 2026-04-27: Created — Phase 1 foundation ticket
