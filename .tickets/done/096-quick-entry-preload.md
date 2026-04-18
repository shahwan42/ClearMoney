---
id: "096"
title: "Quick-entry sheet pre-load form"
type: improvement
priority: medium
status: done
created: 2026-03-31
updated: 2026-04-18
---

## Description

Quick-entry bottom sheet opens empty — user must tap a tab (Transaction or Move Money) before any form appears. Pre-load the transaction form so the sheet is immediately usable.

## Acceptance Criteria

- [x] Transaction form loads automatically when quick-entry sheet opens
- [x] Transaction tab visually selected by default
- [x] No empty state visible to user
- [x] Move Money tab still loads its form on click (lazy load is fine)
- [x] Form fields are focusable immediately (amount field auto-focused)
- [x] Works on repeat opens (form resets between opens)
- [x] E2E test for opening sheet → form immediately visible

## Technical Notes

- Current: `bottom-nav.html:53-72` — tabs trigger HTMX load on click
- Fix: add `hx-trigger="load"` on the Transaction tab's content div, or inline the form HTML
- Alternative: set `hx-trigger="intersect once"` on the sheet content area
- Must clear form state on sheet close to prevent stale data on reopen

## Implementation

- `bottom-nav.html:74-78`: Added `hx-get`, `hx-trigger="load"`, `hx-swap` to content div
- `quick-entry.js:16-27`: Removed URL param from `openQuickEntry()`, added form reset on close
- `test_quick_entry.py:76-117`: Added 2 E2E tests for immediate load and form reset

## Progress Notes

- 2026-03-31: Created — eliminates empty-sheet friction on FAB tap
- 2026-04-18: Implemented — HTMX auto-load + form reset + E2E tests
