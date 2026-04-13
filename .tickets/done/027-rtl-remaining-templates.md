---
id: "027"
title: "RTL — transactions + remaining app templates"
type: feature
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-13
---

## Description

Convert physical Tailwind directional classes to logical equivalents in all remaining app templates: transactions (22), budgets (2), people (4), recurring (3), virtual_accounts (3), reports (5), investments (1), exchange_rates (1), settings_app (2).

## Acceptance Criteria

- [x] All physical directional classes replaced with logical equivalents across ~43 templates
- [x] Transaction list, forms, transfer/exchange flows render correctly in RTL
- [x] Budget progress bars, people/loan lists render correctly in RTL
- [x] Reports charts and settings page render correctly in RTL
- [x] No visual regressions in LTR mode

## Dependencies

- Ticket #025 (RTL shared components)

## Files

- `backend/transactions/templates/transactions/` (22 files)
- `backend/budgets/templates/budgets/` (2 files)
- `backend/people/templates/people/` (4 files)
- `backend/recurring/templates/recurring/` (3 files)
- `backend/virtual_accounts/templates/virtual_accounts/` (3 files)
- `backend/reports/templates/reports/` (5 files)
- `backend/investments/templates/investments/` (1 file)
- `backend/exchange_rates/templates/exchange_rates/` (1 file)
- `backend/settings_app/templates/settings_app/` (2 files)

## Progress Notes

- 2026-03-30: Created — RTL for remaining app templates
- 2026-04-13: Completed — Replaced all physical directional classes (mr-1→me-1, ml-3→ms-3, ml-4→ms-4, text-right→text-end, text-left→text-start, right-0→end-0); fixed chart_trend.html shared component; 1252 tests pass, lint clean
