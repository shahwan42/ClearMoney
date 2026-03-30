---
id: "025"
title: "RTL — shared components + base layout"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Convert physical Tailwind directional classes to logical equivalents in shared templates and add RTL overrides in `app.css`. This ensures the base layout and navigation work correctly in RTL mode.

## Acceptance Criteria

- [ ] Physical Tailwind classes replaced with logical equivalents in shared templates:
  - `ml-` → `ms-`, `mr-` → `me-`, `pl-` → `ps-`, `pr-` → `pe-`
  - `left-` → `start-`, `right-` → `end-`
  - `text-left` → `text-start`, `text-right` → `text-end`
- [ ] RTL overrides added in `static/css/app.css` for scroll shadows, absolute positioning
- [ ] Navigation, header, bottom nav render correctly in both LTR and RTL
- [ ] Error pages (404, 429, 500) render correctly in RTL
- [ ] Visual verification in both modes

## Dependencies

- Ticket #024 (base.html RTL config)

## Files

- `backend/templates/base.html`
- `backend/templates/components/header.html`
- `backend/templates/components/bottom-nav.html`
- `backend/templates/components/bottom_sheet.html`
- `backend/templates/404.html`, `429.html`, `500.html`
- `static/css/app.css`

## Progress Notes

- 2026-03-30: Created — RTL for shared layout components
