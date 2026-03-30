---
id: "027"
title: "RTL — transactions + remaining app templates"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Convert physical Tailwind directional classes to logical equivalents in all remaining app templates: transactions (22), budgets (2), people (4), recurring (3), virtual_accounts (3), reports (5), investments (1), exchange_rates (1), settings_app (2).

## Acceptance Criteria

- [ ] All physical directional classes replaced with logical equivalents across ~43 templates
- [ ] Transaction list, forms, transfer/exchange flows render correctly in RTL
- [ ] Budget progress bars, people/loan lists render correctly in RTL
- [ ] Reports charts and settings page render correctly in RTL
- [ ] No visual regressions in LTR mode

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
