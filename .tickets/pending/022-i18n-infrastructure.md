---
id: "022"
title: "i18n infrastructure — settings, middleware, locale dirs"
type: feature
priority: high
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Set up Django's built-in internationalization framework as the foundation for Arabic localization. This is the first ticket in the Arabic localization epic and must be completed before all others.

## Acceptance Criteria

- [ ] `LANGUAGES = [("en", "English"), ("ar", "العربية")]` added to `settings.py`
- [ ] `LOCALE_PATHS` configured pointing to `backend/locale/`
- [ ] `django.middleware.locale.LocaleMiddleware` added to middleware stack (after session middleware)
- [ ] `django.template.context_processors.i18n` added to template context processors
- [ ] `backend/locale/en/LC_MESSAGES/` and `backend/locale/ar/LC_MESSAGES/` directories created
- [ ] Makefile targets added: `make messages` (`makemessages -l ar`) and `make compile-messages` (`compilemessages`)
- [ ] One test string wrapped with `{% trans %}` in `base.html` to verify end-to-end flow
- [ ] `.po` file generated with `make messages`, Arabic translation added, compiled with `make compile-messages`
- [ ] `make test` passes, `make lint` clean

## Files

- `backend/clearmoney/settings.py`
- `backend/templates/base.html`
- `backend/locale/ar/LC_MESSAGES/django.po`
- `backend/locale/en/LC_MESSAGES/django.po`
- `Makefile`

## Progress Notes

- 2026-03-30: Created — Foundation ticket for Arabic localization epic
