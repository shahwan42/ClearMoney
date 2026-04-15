---
id: "047"
title: "Decompose get_dashboard (125 lines)"
type: refactor
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-15
---

## Description

`DashboardService.get_dashboard()` in `dashboard/services/__init__.py` (lines ~137-278) is 125 lines calling 17 different sub-services, each wrapped in try/except for fault tolerance. Group related data loads into domain-focused orchestration methods.

## Acceptance Criteria

- [x] Extract `_load_core_data()` — institutions, accounts, net worth
- [x] Extract `_load_financial_summary()` — CC, debt, investments
- [x] Extract `_load_activity_data()` — transactions, streak, spending
- [x] Extract `_load_sparklines()` — all sparkline methods
- [x] Extract `_load_constraints()` — budgets, health warnings
- [x] Compose in a shorter `get_dashboard()` orchestrator
- [x] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
- 2026-04-15: Completed — Refactored get_dashboard() from 125 lines into 5 domain-focused sub-methods. Added 5 unit tests for sub-methods. All 1314 tests passing, zero lint errors. No behavior changes, all error handling preserved.
