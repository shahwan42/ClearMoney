---
id: "038"
title: "Category name → JSONB migration"
type: feature
priority: high
status: done
created: 2026-03-30
updated: 2026-04-14
---

## Description

Migrate the Category `name` field from `CharField` to `JSONField` to support multilingual category names. Store names as `{"en": "Food", "ar": "طعام"}`. This is a multi-step migration to avoid data loss.

## Acceptance Criteria

- [x] Multi-step migration:
  1. Add `name_json = JSONField(default=dict, null=True)` alongside existing `name`
  2. Data migration: copy existing `name` values into `name_json` as `{"en": <current_name>}`
  3. Drop old `name` column, rename `name_json` → `name`
- [x] `Category.get_display_name(lang=None)` method added — returns name for active language, falls back to English
- [x] Template filter or helper for displaying category name based on active language
- [x] All category reads updated to use `get_display_name()` instead of raw `.name`
- [x] Category creation/update services updated to store JSONB format
- [x] All existing tests updated and passing
- [x] `make test` passes, `make lint` clean
- [x] Backward-compatible: existing categories get `{"en": "old_name"}` with no data loss

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/categories/models.py`
- `backend/categories/services.py`
- `backend/categories/migrations/` (3 new migration files: 0003, 0004, 0005)
- `backend/auth_app/services.py` (category seeding with Arabic names)
- `backend/core/templatetags/money.py` (categories_json + category_name filter)
- `backend/transactions/services/crud.py` (raw SQL: `c.name->>'en'`)
- `backend/transactions/services/activity.py` (get_display_name())
- `backend/transactions/services/helpers.py` (KeyTextTransform)
- `backend/transactions/services/transfers.py` (name__en lookup)
- `backend/accounts/services.py` (KeyTextTransform)
- `backend/budgets/services.py` (KeyTextTransform + get_display_name())
- `backend/budgets/views.py` (KeyTextTransform)
- `backend/dashboard/services/spending.py` (KeyTextTransform + Coalesce)
- `backend/reports/services.py` (KeyTextTransform)
- `backend/recurring/views.py` (KeyTextTransform)
- `backend/core/migrations/0007_add_system_categories.py` (JSONB insert)
- `backend/tests/factories.py` (CategoryFactory name default)
- All test files using CategoryFactory

## Progress Notes

- 2026-03-30: Created — JSONB migration for multilingual category names
- 2026-04-14: Implemented — 3-step migration, all services/templates/tests updated. 1252 tests pass, lint clean. Arabic names added to all 27 seeded categories.
