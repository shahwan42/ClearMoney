---
id: "041"
title: "Extract shared month-range utilities to core/dates.py"
type: refactor
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Month boundary calculations (first day of month, first day of next month, previous month range) are reimplemented ~8 times across the codebase with identical logic. Extract into a shared `core/dates.py` module.

## Duplicated Locations

- `budgets/services.py` — `_month_range()` (lines ~267-275) and inline in `get_all_with_spending` (lines ~52-56)
- `accounts/services.py` — inline in `load_health_warnings` (lines ~789-793)
- `dashboard/services/spending.py` — this/last/next month calculations (lines ~52-64)
- `reports/services.py` — inline month boundaries (lines ~91-92, ~139, ~177-184)
- `people/services.py` — inline in balance lookup (lines ~323-327)

## Acceptance Criteria

- [x] Create `backend/core/dates.py` with `month_range(date)`, `prev_month_range(date)`, `next_month_range(date)` helpers
- [x] Replace all inline month calculations with calls to shared helpers
- [x] Add unit tests for edge cases (December→January rollover, leap year February)
- [x] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
- 2026-04-15: Completed — created core/dates.py, updated 4 service files, 13 new tests pass, all 1265 tests pass
