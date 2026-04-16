---
id: "058"
title: "Transfer variant tests: Fawry + InstaPay"
type: test
priority: medium
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

`transactions/services/transfers.py` is at 89.29% (18 uncovered lines). The gaps are in Fawry cashout validation/balance updates (lines 379-434), InstaPay fee application to source balance (lines 170-187), and default date handling (line 67). These are financial operations that modify account balances.

## Acceptance Criteria

- [x] Test `create_fawry_cashout()` happy path — balance updates for both accounts
- [x] Test Fawry cashout with invalid account IDs
- [x] Test Fawry same-account validation returns error
- [x] Test Fawry fee handling
- [x] Test InstaPay fee deduction from source account balance
- [x] Test `tx_date=None` defaults to `date.today()` (line 67)
- [x] transfers.py coverage reaches at least 93%
- [x] All existing tests still pass

## Files

- `backend/transactions/services/transfers.py` — lines 67, 170-187, 379-434
- `backend/transactions/tests/test_services.py` — add new test classes

## Estimated Size

Medium — 5-6 new tests, no code changes needed.

## Progress Notes

- 2026-03-31: Created — identified gaps in financial transfer operations during coverage analysis
