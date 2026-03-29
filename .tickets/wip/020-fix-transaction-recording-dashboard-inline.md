---
id: "020"
title: "Fix dashboard rendering inline after quick entry"
type: bug
priority: high
status: wip
created: 2026-03-29
updated: 2026-03-29
---

## Description

After recording a transaction via quick entry, the dashboard net-worth and accounts panels render inline within the success message area, instead of only showing the success message and action buttons.

Root cause: `quick_entry_create` view appends two `<div>` elements with `hx-get` and `hx-trigger="load"` to the response, but without `hx-swap-oob="true"`. HTMX includes them in the main innerHTML swap into `#quick-entry-result`, causing dashboard content to load inside the success area.

## Acceptance Criteria

- [x] After quick entry, only success message and action buttons are visible
- [x] Dashboard panels (net-worth, accounts) refresh via OOB swap, not inline
- [x] Existing tests updated and passing

## Progress Notes

- 2026-03-29: Started — Identified root cause in quick_entry_create view (missing hx-swap-oob)
