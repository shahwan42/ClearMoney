---
id: "030"
title: "i18n strings — dashboard templates"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Wrap all hardcoded English strings in dashboard templates with Django translation tags. Add Arabic translations. Dashboard is the most-visited page.

## Acceptance Criteria

- [ ] `{% load i18n %}` added to all 15 dashboard templates
- [ ] ~40 strings extracted: "Net Worth", "Liquid Cash", "Credit Used", "Recent Transactions", "View All", empty state text, panel headings
- [ ] Arabic translations added to `.po` file
- [ ] Dashboard renders correctly in both languages with all panels
- [ ] `make test` and `make test-e2e` pass

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/dashboard/templates/dashboard/` (all 15 files)
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for dashboard templates
