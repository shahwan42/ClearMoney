---
id: "144"
title: "Generalized dashboard people summary and debt aggregation"
type: feature
priority: high
status: done
created: 2026-04-22
updated: 2026-04-23
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

- [x] Dashboard people summary supports any active currency
- [x] Debt aggregation no longer assumes exactly two currencies
- [x] Selected-currency values can be derived from the generalized output
- [x] Dashboard templates no longer depend on fixed EGP/USD people-summary data

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
- 2026-04-23: Started — moving dashboard people summary and debt breakdown off fixed EGP/USD fields onto generalized person currency balances, with selected-currency helpers for dashboard cards.
- 2026-04-23: Completed — switched dashboard people/debt aggregation to generalized person currency balances with legacy fallback, added selected-currency people/debt helpers for dashboard consumers, updated the dashboard people partial to render the selected-currency slice, and verified with full backend (`1550 passed`) and full E2E (`272 passed`) suites.
