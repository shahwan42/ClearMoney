---
id: "143"
title: "Dynamic people UI and debt summary contracts"
type: feature
priority: high
status: done
created: 2026-04-22
updated: 2026-04-23
---

## Description

Convert people list and detail rendering from fixed EGP/USD sections to dynamic
currency rows, and update service contracts so people summaries can emit
arbitrary per-currency data.

## Details

- Replace hard-coded people template branches for `net_balance_egp` and
  `net_balance_usd`
- Update currency-breakdown helpers to iterate dynamic balances instead of a
  two-currency list
- Keep existing sign semantics: positive means they owe me, negative means I owe
  them
- Define deterministic display ordering for multi-currency balances
- Preserve payoff/progress behavior while separating it from dual-currency fields

## Acceptance Criteria

- [x] People list and detail pages render any number of currencies
- [x] No people template references `net_balance_egp` or `net_balance_usd`
- [x] Currency-breakdown output is dynamic and deterministic
- [x] Existing EGP/USD users see unchanged results after migration
- [x] Progress and payoff data remain correct with multi-currency balances

## Critical Files

- `backend/people/services.py`
- `backend/people/templates/people/_person_card.html`
- `backend/people/templates/people/person_detail.html`
- `backend/people/templates/people/_debt_progress.html`
- `backend/people/views.py`

## Unit Tests

- Dynamic per-currency ordering
- Multi-currency debt breakdown calculations
- Progress and payoff calculations with multiple currencies present

## E2E Tests

- Person card with three currencies
- Person detail page with dynamic balance rows
- Loan and repayment actions immediately update rendered summaries

## Dependencies

- Depends on `#142`

## Progress Notes

- 2026-04-22: Created to consume generalized people balances from `#142`
- 2026-04-23: Started implementation from `wip`; verified current dynamic balance rendering, then targeted remaining contract gaps around deterministic ordering and multi-currency progress/payoff semantics.
- 2026-04-23: Completed — added dynamic active-balance rows in people list/detail, extended debt-summary contracts with per-currency projected payoff data and mixed-currency-safe top-level progress/payoff behavior, updated people docs, and verified with full backend (`1547 passed`) plus full E2E (`272 passed`) suites.
