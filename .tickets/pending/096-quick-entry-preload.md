---
id: "096"
title: "Quick-entry sheet pre-load form"
type: improvement
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Quick-entry bottom sheet opens empty — user must tap a tab (Transaction or Move Money) before any form appears. Pre-load the transaction form so the sheet is immediately usable.

## Acceptance Criteria

- [ ] Transaction form loads automatically when quick-entry sheet opens
- [ ] Transaction tab visually selected by default
- [ ] No empty state visible to user
- [ ] Move Money tab still loads its form on click (lazy load is fine)
- [ ] Form fields are focusable immediately (amount field auto-focused)
- [ ] Works on repeat opens (form resets between opens)
- [ ] E2E test for opening sheet → form immediately visible

## Technical Notes

- Current: `bottom-nav.html:53-72` — tabs trigger HTMX load on click
- Fix: add `hx-trigger="load"` on the Transaction tab's content div, or inline the form HTML
- Alternative: set `hx-trigger="intersect once"` on the sheet content area
- Must clear form state on sheet close to prevent stale data on reopen

## Progress Notes

- 2026-03-31: Created — eliminates empty-sheet friction on FAB tap
