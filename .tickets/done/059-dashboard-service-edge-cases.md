---
id: "059"
title: "Dashboard service edge case tests"
type: test
priority: low
status: done
created: 2026-03-31
updated: 2026-03-31
---

## Description

`dashboard/services/` is at 89.4% coverage (62 uncovered lines across multiple modules). Gaps include exchange rate fallback when rate=0, currency conversion with missing rates, net worth breakdown filtering for all card types, spending velocity threshold boundaries, and month boundary / year-end transitions.

## Acceptance Criteria

- [x] Test exchange rate fallback: rate=0 or missing rate in `services/accounts.py` (lines 100-108)
- [x] Test currency conversion with zero/missing exchange rate (lines 77-84)
- [x] Test net worth breakdown for all card type filters (lines 138-200)
- [x] Test spending velocity at exact threshold boundaries (services/spending.py lines 143-148)
- [x] Test month boundary: December → January transition (spending.py lines 54-64)
- [x] Test top categories with no data and all-uncategorized scenarios
- [x] dashboard coverage reaches at least 92%
- [x] All existing tests still pass

## Files

- `backend/dashboard/services/accounts.py` — exchange rate + breakdown gaps
- `backend/dashboard/services/spending.py` — velocity + month boundary gaps
- `backend/dashboard/tests/test_services.py` — add new test functions

## Estimated Size

Medium — 6-8 new tests, no code changes needed.

## Progress Notes

- 2026-03-31: Created — identified dashboard as second-most missed lines during coverage analysis
