---
id: "028"
title: "i18n strings — auth templates"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Wrap all hardcoded English strings in auth templates with Django translation tags. Add Arabic translations to the `.po` file.

## Acceptance Criteria

- [ ] `{% load i18n %}` added to all auth templates
- [ ] All static text wrapped with `{% trans %}` or `{% blocktrans %}`
- [ ] ~20 strings extracted: login form labels, email prompts, error messages, "ClearMoney" branding text
- [ ] Arabic translations added to `locale/ar/LC_MESSAGES/django.po`
- [ ] `make compile-messages` succeeds
- [ ] Auth pages render correctly in both English and Arabic
- [ ] `make test` passes

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
