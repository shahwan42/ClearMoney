---
id: "037"
title: "i18n — push notifications + email template"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Wrap push notification titles/bodies and the magic link email template with translation functions so they render in the user's language.

## Acceptance Criteria

- [ ] `push/services.py`: notification titles and bodies wrapped with `gettext()` (not lazy — evaluated at request time)
  - "Credit Card Due Soon", "Budget Exceeded", "Budget Warning", "Recurring Transaction Due", "Account Health Warning"
- [ ] `auth_app/services.py` `send_magic_link()`: email subject, body text, button text wrapped with `gettext()`
- [ ] Email HTML includes `dir="rtl"` when rendering for Arabic users
- [ ] Arabic translations added to `.po` file
- [ ] Notifications display in Arabic when user language is Arabic
- [ ] Email renders correctly in both LTR and RTL
- [ ] `make test` passes, `make lint` clean

## Dependencies

- Ticket #023 (user language preference — needed to know user's language at email/notification time)

## Files

- `backend/push/services.py`
- `backend/auth_app/services.py`
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for push notifications and email template
