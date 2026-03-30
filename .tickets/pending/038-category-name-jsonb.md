---
id: "038"
title: "Category name → JSONB migration"
type: feature
priority: high
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Migrate the Category `name` field from `CharField` to `JSONField` to support multilingual category names. Store names as `{"en": "Food", "ar": "طعام"}`. This is a multi-step migration to avoid data loss.

## Acceptance Criteria

- [ ] Multi-step migration:
  1. Add `name_json = JSONField(default=dict, null=True)` alongside existing `name`
  2. Data migration: copy existing `name` values into `name_json` as `{"en": <current_name>}`
  3. Drop old `name` column, rename `name_json` → `name`
- [ ] `Category.get_display_name(lang=None)` method added — returns name for active language, falls back to English
- [ ] Template filter or helper for displaying category name based on active language
- [ ] All category reads updated to use `get_display_name()` instead of raw `.name`
- [ ] Category creation/update services updated to store JSONB format
- [ ] All existing tests updated and passing
- [ ] `make test` passes, `make lint` clean
- [ ] Backward-compatible: existing categories get `{"en": "old_name"}` with no data loss

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/categories/models.py`
- `backend/categories/services.py`
- `backend/categories/migrations/` (2-3 new migration files)
- `backend/auth_app/services.py` (category seeding)
- Templates referencing `category.name` (multiple apps)
- `backend/core/templatetags/money.py` (if category display filter exists)

## Progress Notes

- 2026-03-30: Created — JSONB migration for multilingual category names
