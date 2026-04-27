---
id: "512"
title: "Currency bilingual names (JSONB)"
type: feature
priority: medium
status: done
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

- [x] `Currency.name` is JSONB with `{"en": ..., "ar": ...}` for all 6 currencies
- [x] `get_display_name(lang)` method on Currency mirrors Category/SystemBank pattern
- [x] Settings page shows Arabic currency names in Arabic mode (template renders `currency.name` from `CurrencyOption`, which now resolves bilingual at the service layer)
- [x] People + account forms get the same locale-aware names through `get_user_active_currencies` → `get_supported_currencies()`
- [x] Migration is safe — single migration uses `SeparateDatabaseAndState` with explicit `ALTER TABLE ... TYPE jsonb USING jsonb_build_object('en', name)` (Django's auto-USING fails on non-JSON strings). RunPython then adds Arabic. Reverse migration restores VARCHAR(50).
- [x] Django system check passes
- [x] Unit tests: 9 cases covering en/ar/region/missing/empty/code-fallback, settings-view bilingual resolution, all 6 currencies have both locales
- [x] `make test && make lint` pass — 1824 tests, ruff + mypy clean

## Affected User Journeys

- J-3, J-4 (Account/Budget mgmt forms): currency dropdowns now show Arabic names in Arabic mode.

## Deviations from spec

- Single migration instead of two-step (the ticket suggested two steps for production-safety). The `currencies` table holds 6 rows and is changed at the column-type level only — wrapped in `SeparateDatabaseAndState` so Django's state stays consistent. Single migration is reversible end-to-end (the SQL has explicit reverse). This is the same level of risk as the two-step approach with much less complexity.

## Dependencies

- None (standalone Phase 2 ticket)

## Progress Notes

- 2026-04-27: Created — Phase 2 currency bilingual ticket
- 2026-04-27: Completed — Migration `auth_app/0010_currency_name_to_jsonb.py` converts `name` column to jsonb in-place, populates Arabic for all 6 seeded currencies. Updated `get_supported_currencies()` to call `get_display_name()`. Extended autouse seed fixture in `conftest.py` to re-seed currencies (and detect non-bilingual rows from older test runs) alongside system_banks.
