---
id: "034"
title: "i18n strings — recurring + investments + reports + settings + exchange rates"
type: feature
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-14
---

## Description

Wrap all hardcoded English strings in remaining app templates with Django translation tags. Add Arabic translations.

## Acceptance Criteria

- [x] `{% load i18n %}` added to all 12 templates (recurring 3, investments 1, reports 5, settings_app 2, exchange_rates 1)
- [x] ~25 strings extracted: recurring rule labels, investment tracking text, report headings/legends, settings labels, exchange rate labels
- [x] Arabic translations added to `.po` file
- [x] All pages render correctly in both languages
- [x] `make test` passes

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/recurring/templates/recurring/` (3 files)
- `backend/investments/templates/investments/` (1 file)
- `backend/reports/templates/reports/` (5 files)
- `backend/settings_app/templates/settings_app/` (2 files)
- `backend/exchange_rates/templates/exchange_rates/` (1 file)
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for remaining app templates
- 2026-04-14: Completed — added {% load i18n %} + trans tags to all 12 templates, ran makemessages + compilemessages, all 1252 tests pass