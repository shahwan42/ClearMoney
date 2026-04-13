---
id: "025"
title: "RTL — shared components + base layout"
type: feature
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-13
---

## Description

Convert physical Tailwind directional classes to logical equivalents in shared templates and add RTL overrides in `app.css`. This ensures the base layout and navigation work correctly in RTL mode.

## Acceptance Criteria

- [x] Physical Tailwind classes replaced with logical equivalents in shared templates:
  - `ml-` → `ms-`, `mr-` → `me-`, `pl-` → `ps-`, `pr-` → `pe-`
  - `left-` → `start-`, `right-` → `end-`
  - `text-left` → `text-start`, `text-right` → `text-end`
- [x] RTL overrides added in `static/css/app.css` for scroll shadows, absolute positioning
- [x] Navigation, header, bottom nav render correctly in both LTR and RTL
- [x] Error pages (404, 429, 500) render correctly in RTL
- [x] Visual verification in both modes

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
- 2026-04-13: Completed — Replaced all physical directional classes with logical equivalents (ms-, me-, start-, end-); added [dir="rtl"] scroll-shadow overrides in app.css; 1231 tests pass, lint clean
