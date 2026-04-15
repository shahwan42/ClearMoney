---
id: "036"
title: "i18n — auth + validation error messages"
type: feature
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-15
---

## Description

Wrap all user-facing error and validation messages in service layer files with `gettext_lazy()` or `gettext()` so they display in the user's language.

## Acceptance Criteria

- [ ] `auth_app/services.py`: rate limit messages (REUSED, COOLDOWN, DAILY_LIMIT, GLOBAL_CAP) and validation errors wrapped
- [ ] `transactions/services/crud.py`: "Amount must be positive", "account_id is required", "Would exceed credit limit" etc. wrapped
- [ ] `categories/services.py`: "category name is required", "already exists", "system categories cannot be modified" etc. wrapped
- [ ] `accounts/services.py`: validation errors and health warning messages wrapped
- [ ] Arabic translations added to `.po` file
- [ ] Error messages display in Arabic when user language is Arabic
- [ ] `make test` passes, `make lint` clean

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/auth_app/services.py`
- `backend/transactions/services/crud.py`
- `backend/categories/services.py`
- `backend/accounts/services.py`
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for service-layer validation errors
- 2026-04-14: Completed — All service-layer error messages wrapped with gettext/gettext_lazy. Arabic translations added to .po file. All 1252 tests pass, lint clean.
