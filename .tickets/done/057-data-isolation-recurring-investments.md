---
id: "057"
title: "Data isolation tests: recurring + investments"
type: test
priority: medium
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

The central `test_data_isolation.py` covers accounts, institutions, transactions, budgets, virtual_accounts, people, and categories. Missing: **recurring rules** and **investments**. These apps filter by `user_id` but have no cross-user isolation tests in the isolation suite.

## Acceptance Criteria

- [x] Add `test_recurring_rules_isolated` — User B cannot see User A's recurring rules
- [x] Add `test_recurring_rule_by_id_isolated` — User B cannot fetch User A's rule by ID
- [x] Add `test_investments_isolated` — User B cannot see User A's investments
- [x] Add `test_investment_by_id_isolated` — User B cannot fetch User A's investment by ID
- [x] All tests pass, no regressions

## Files

- `backend/tests/test_data_isolation.py` — add 3-4 new test methods to `TestDataIsolation`
- Verify: `backend/recurring/services.py` and `backend/investments/services.py` filter by `user_id`

## Estimated Size

Small — 3-4 new tests, no code changes needed.

## Progress Notes

- 2026-03-31: Created — identified missing apps in isolation test suite during coverage analysis
- 2026-04-16: Done — Added isolation tests for recurring rules and investments using the appropriate factories and services.
