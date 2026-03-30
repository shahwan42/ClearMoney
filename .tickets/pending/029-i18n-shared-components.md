---
id: "029"
title: "i18n strings — shared components + error pages"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Wrap all hardcoded English strings in shared components (header, nav, bottom sheet, charts) and error pages with Django translation tags. Add Arabic translations.

## Acceptance Criteria

- [ ] `{% load i18n %}` added to all shared component templates
- [ ] ~25 strings extracted: HTMX error messages, nav items, chart labels, error page text
- [ ] Arabic translations added to `.po` file
- [ ] Inline JS strings in `base.html` (HTMX error handlers) translated
- [ ] All shared components render correctly in both languages
- [ ] `make test` passes

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/templates/base.html`
- `backend/templates/components/header.html`
- `backend/templates/components/bottom-nav.html`
- `backend/templates/components/bottom_sheet.html`
- `backend/templates/components/_institution_icon.html`
- `backend/templates/components/chart_*.html`
- `backend/templates/404.html`, `429.html`, `500.html`
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for shared components and error pages
