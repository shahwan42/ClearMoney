---
id: "144"
title: "Generalized dashboard people summary and debt aggregation"
type: feature
priority: high
status: pending
created: 2026-04-22
updated: 2026-04-22
---

## Description

Remove dual-currency assumptions from dashboard people-summary and debt
aggregation logic so dashboard cards can consume generalized per-currency data.

## Details

- Replace fixed `PeopleCurrencySummary(currency=\"EGP\"/\"USD\")` flows
- Aggregate debt from generalized person balance rows
- Expose per-currency totals plus selected-currency slices for dashboard cards
- Preserve current debt semantics and sign handling
- Update dashboard templates to consume dynamic collections

## Acceptance Criteria

- [ ] Dashboard people summary supports any active currency
- [ ] Debt aggregation no longer assumes exactly two currencies
- [ ] Selected-currency values can be derived from the generalized output
- [ ] Dashboard templates no longer depend on fixed EGP/USD people-summary data

## Critical Files

- `backend/dashboard/services/activity.py`
- `backend/dashboard/services/__init__.py`
- `backend/dashboard/templates/dashboard/_people_summary.html`
- `backend/dashboard/services/accounts.py`

## Unit Tests

- People summary with third-currency balances
- Debt aggregation grouped by arbitrary currency
- Selected-currency extraction from generalized summary output

## E2E Tests

- Dashboard people summary changes when the selected currency changes
- Mixed-currency users only see the relevant selected-currency summary

## Dependencies

- Depends on `#142`
- Builds on `#143`

## Progress Notes

- 2026-04-22: Created for dashboard-side people/debt generalization

