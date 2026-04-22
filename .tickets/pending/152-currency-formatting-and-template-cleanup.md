---
id: "152"
title: "Currency formatting and template cleanup"
type: improvement
priority: medium
status: pending
created: 2026-04-22
updated: 2026-04-22
---

## Description

Make formatting helpers and templates fully currency-generic so dynamic
surfaces render arbitrary supported currencies cleanly and no longer depend on
fixed-currency filters or branches.

## Details

- Audit `format_currency` and related template tags for arbitrary currency codes
- Remove lingering `format_egp` / `format_usd`-style assumptions from dynamic
  surfaces
- Standardize fallback formatting for currencies without custom symbols
- Keep symbol support where it exists without making product logic depend on it

## Acceptance Criteria

- [ ] Third-currency values render correctly across the app
- [ ] Dynamic templates do not depend on fixed-currency formatting branches
- [ ] Supported currencies without a custom symbol remain readable

## Critical Files

- `backend/core/templatetags/money.py`
- `backend/people/templates/people/`
- `backend/dashboard/templates/dashboard/`
- `backend/budgets/templates/budgets/`
- `backend/reports/templates/reports/`

## Unit Tests

- Formatting for `EGP`, `USD`, and at least one additional currency
- Fallback formatting for currencies without a symbol mapping
- Null and invalid formatting behavior

## E2E Tests

- Major screens render a third currency consistently
- Screens using selected-currency summaries do not regress formatting

## Dependencies

- Depends on `#143`
- Depends on `#146`
- Depends on `#149`

## Progress Notes

- 2026-04-22: Created for currency-generic formatting cleanup

