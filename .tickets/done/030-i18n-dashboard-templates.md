---
id: "030"
title: "i18n strings — dashboard templates"
type: feature
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-14
---

## Description

Wrap all hardcoded English strings in dashboard templates with Django translation tags. Add Arabic translations. Dashboard is the most-visited page.

## Acceptance Criteria

- [x] `{% load i18n %}` added to all 15 dashboard templates
- [x] ~40 strings extracted: "Net Worth", "Liquid Cash", "Credit Used", "Recent Transactions", "View All", empty state text, panel headings
- [x] Arabic translations added to `.po` file
- [x] Dashboard renders correctly in both languages with all panels
- [x] `make test` and `make test-e2e` pass

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/dashboard/templates/dashboard/` (all 15 files)
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for dashboard templates
- 2026-04-14: Completed — all 15 templates updated with i18n tags, Arabic translations added, 1252 unit tests + 158 e2e tests pass
