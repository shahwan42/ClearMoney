---
id: "042"
title: "Extract status/threshold computation to core/status.py"
type: refactor
priority: low
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Red/amber/green status computation based on percentage thresholds is duplicated in budgets, dashboard spending, and push notification services. Extract into a shared helper.

## Duplicated Locations

- `budgets/services.py` — budget status calculation (lines ~83-95)
- `dashboard/services/spending.py` — spending velocity status (lines ~143-148)
- `push/services.py` — budget threshold alerts (lines ~90-118)

## Acceptance Criteria

- [ ] Create `backend/core/status.py` with `compute_threshold_status(percentage, thresholds)` helper
- [ ] Replace duplicated threshold logic in all three locations
- [ ] Add unit tests for boundary values (exactly at threshold, above, below)
- [ ] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
