---
id: "512"
title: "Currency bilingual names (JSONB)"
type: feature
priority: medium
status: pending
created: 2026-04-27
updated: 2026-04-27
---

## Description

Migrate the `Currency.name` field from plain `CharField` to JSONB, following the same pattern as `Category.name`. Add Arabic translations for all 6 seeded currencies. Update all display sites to use `get_display_name()` method.

## Schema Change

```python
# Before
name = models.CharField(max_length=100)

# After
name = models.JSONField()  # {"en": "Egyptian Pound", "ar": "الجنيه المصري"}
```

Add `get_display_name(lang=None)` method same pattern as `Category`.

## Arabic Translations

| Code | English | Arabic |
|------|---------|--------|
| EGP | Egyptian Pound | الجنيه المصري |
| USD | US Dollar | الدولار الأمريكي |
| EUR | Euro | اليورو |
| GBP | British Pound | الجنيه الإسترليني |
| AED | UAE Dirham | الدرهم الإماراتي |
| SAR | Saudi Riyal | الريال السعودي |

## Migration Strategy

Two-step safe migration (production-safe, additive):

1. **Migration A**: Add `name_new JSONField null=True`, copy existing `name` string to `{"en": name}` for all rows, add Arabic values
2. **Migration B**: Rename `name_new` → `name`, drop old `name` column

(Or single migration that alters column type if PostgreSQL JSONB cast is clean — verify first.)

## Display Sites to Update

- `settings_app/templates/settings_app/settings.html` — currency checkboxes
- `settings_app/views.py` — any currency name references
- `accounts/` templates — currency display in account creation
- Any serializer/service that returns `currency.name` as string

Add `get_display_name()` calls everywhere `currency.name` was used.

## Acceptance Criteria

- [ ] `Currency.name` is JSONB with `{"en": ..., "ar": ...}` for all 6 currencies
- [ ] `get_display_name(lang)` method on `Currency` model
- [ ] Settings page shows Arabic currency names in Arabic mode
- [ ] Account creation form shows Arabic currency names in Arabic mode
- [ ] Migration is safe (no data loss, backward-compatible intermediate state)
- [ ] `mcp__django-ai-boost__run_check` passes
- [ ] Unit tests: `get_display_name` with en/ar/None; display in settings view
- [ ] `make test && make lint` pass

## Dependencies

- None (standalone Phase 2 ticket)

## Progress Notes

- 2026-04-27: Created — Phase 2 currency bilingual ticket
