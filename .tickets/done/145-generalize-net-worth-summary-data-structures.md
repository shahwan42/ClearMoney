---
id: "145"
title: "Generalize net worth summary data structures"
type: feature
priority: high
status: done
created: 2026-04-22
updated: 2026-04-23
---

## Description

Redesign net-worth summary structures so account, debt, and cash totals are
represented as generalized per-currency aggregates rather than fixed EGP/USD
fields.

## Details

- Replace fields like `egp_total`, `usd_total`, `cash_usd`, `debt_egp`, and
  `debt_usd` with generalized per-currency structures
- Update `compute_net_worth()` and related helpers to emit dynamic totals,
  debt, liquid cash, and credit-related values
- Remove fallback logic that buckets non-USD values into EGP-oriented fields
- Keep exact-currency math with no display-time conversion

## Acceptance Criteria

- [x] Net-worth computation is currency-agnostic
- [x] Third currencies are represented explicitly, not folded into EGP buckets
- [x] Dashboard callers can render selected-currency values without conversion
- [x] Credit-used and credit-available logic remains correct across currencies

## Critical Files

- `backend/accounts/types.py`
- `backend/accounts/services.py`
- `backend/dashboard/services/accounts.py`
- `backend/dashboard/services/__init__.py`

## Unit Tests

- Net-worth summary with three currencies
- Debt split across three currencies
- Credit-used and credit-available calculations across currencies
- Regression coverage for prior EGP-bucket fallback behavior

## E2E Tests

- Dashboard net-worth cards reflect only the selected currency
- Breakdown views remain consistent with the selected-currency slice

## Dependencies

- Depends on `#142`

## Progress Notes

- 2026-04-22: Created for generalized net-worth data contracts
- 2026-04-23: Implemented generalized NetWorthSummary and DashboardData with dicts. Updated compute_net_worth and template to iterate over all currencies. All tests passed.
