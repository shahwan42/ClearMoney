---
id: "028"
title: "i18n strings — auth templates"
type: feature
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-14
---

## Description

Wrap all hardcoded English strings in auth templates with Django translation tags. Add Arabic translations to the `.po` file.

## Acceptance Criteria

- [x] `{% load i18n %}` added to all auth templates
- [x] All static text wrapped with `{% trans %}` or `{% blocktrans %}`
- [x] ~20 strings extracted: login form labels, email prompts, error messages, "ClearMoney" branding text
- [x] Arabic translations added to `locale/ar/LC_MESSAGES/django.po`
- [x] `make compile-messages` succeeds
- [x] Auth pages render correctly in both English and Arabic
- [x] `make test` passes

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/auth_app/templates/auth_app/auth.html`
- `backend/auth_app/templates/auth_app/check_email.html`
- `backend/auth_app/templates/auth_app/link_expired.html`
- `backend/auth_app/templates/auth_app/bare.html`
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for auth templates
- 2026-04-14: Done — `{% load i18n %}` + `{% trans %}` / `{% blocktrans %}` tags added to auth.html, check_email.html, link_expired.html; 16 Arabic translations added; compile-messages succeeds; 1252 tests pass.
