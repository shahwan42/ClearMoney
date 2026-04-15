---
id: "042"
title: "Extract status/threshold computation to core/status.py"
type: refactor
priority: low
status: done
created: 2026-03-30
updated: 2026-04-15
---

## Description

Red/amber/green status computation based on percentage thresholds is duplicated in budgets, dashboard spending, and push notification services. Extract into a shared helper.

## Duplicated Locations

- `budgets/services.py` — budget status calculation (lines ~83-95)
- `dashboard/services/spending.py` — spending velocity status (lines ~143-148)
- `push/services.py` — budget threshold alerts (lines ~90-118)

## Acceptance Criteria

- [x] Create `backend/core/status.py` with `compute_threshold_status(percentage, thresholds)` helper
- [x] Replace duplicated threshold logic in all three locations
- [x] Add unit tests for boundary values (exactly at threshold, above, below)
- [x] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
- 2026-04-15: Implemented — created `core/status.py` with `compute_threshold_status` and `compute_spending_velocity_status`, replaced all 4 duplicated instances across `budgets/services.py` (3), `push/services.py` (1), `dashboard/services/spending.py` (1), added `core/tests/test_status.py` with boundary value tests. All 1278 tests pass, lint passes.
