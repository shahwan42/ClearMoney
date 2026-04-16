---
id: "056"
title: "People debt summary + repayment tests"
type: test
priority: medium
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

`people/services.py` is at 89.14% coverage (19 uncovered lines). The gaps are in complex financial logic: debt summary computation (projected payoff, average repayment), repayment direction based on balance sign, and error paths for missing accounts/people.

## Acceptance Criteria

- [x] Test debt summary with zero debt (no transactions) — lines 432-490
- [x] Test debt summary with single transaction
- [x] Test projected payoff avoids division by zero
- [x] Test repayment direction logic for positive vs negative balance (line 311)
- [x] Test `update()` returns None for nonexistent person (line 172)
- [x] Test account-not-found ValueError in loan operations (line 204)
- [x] Test date parsing edge cases in loans/repayments (lines 252, 340)
- [x] people app coverage reaches at least 92%
- [x] All existing tests still pass

## Files

- `backend/people/services.py` — lines 172, 179, 204, 252, 311, 340, 432-490
- `backend/people/tests/test_services.py` — add new test classes

## Estimated Size

Medium — 6-8 new tests, no code changes needed.

## Progress Notes

- 2026-03-31: Created — identified gaps in complex financial math during test coverage analysis
- 2026-04-16: Completed — Added tests for missing edge cases and division scenarios, coverage is now 96.28%.
