---
id: "023"
title: "User language preference — model + middleware + migration"
type: feature
priority: high
status: done
created: 2026-03-30
updated: 2026-03-30
---

## Description

Add a `language` field to the User model so each user can choose their preferred language. Create a custom `LanguageMiddleware` that reads the user's preference and activates the correct translation.

## Acceptance Criteria

- [ ] `language = CharField(max_length=5, default="en")` added to User model in `auth_app/models.py`
- [ ] Migration generated (additive only — no breaking changes)
- [ ] `LanguageMiddleware` created in `core/middleware.py`
  - Reads authenticated user's `language` field
  - Calls `translation.activate(lang)` to set active language
  - For unauthenticated pages: falls back to `Accept-Language` header or English
- [ ] Middleware added to `settings.py` in correct order (after `GoSessionAuthMiddleware`)
- [ ] Unit tests for middleware: authenticated user gets their language, unauthenticated defaults to English
- [ ] `make test` passes, `make lint` clean

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/auth_app/models.py`
- `backend/auth_app/migrations/` (new migration)
- `backend/core/middleware.py`
- `backend/clearmoney/settings.py`

## Progress Notes

- 2026-03-30: Created — Per-user language preference with middleware
