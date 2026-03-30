---
id: "047"
title: "Decompose get_dashboard (125 lines)"
type: refactor
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

`DashboardService.get_dashboard()` in `dashboard/services/__init__.py` (lines ~137-278) is 125 lines calling 17 different sub-services, each wrapped in try/except for fault tolerance. Group related data loads into domain-focused orchestration methods.

## Acceptance Criteria

- [ ] Extract `_load_core_data()` — institutions, accounts, net worth
- [ ] Extract `_load_financial_summary()` — CC, debt, investments
- [ ] Extract `_load_activity_data()` — transactions, streak, spending
- [ ] Extract `_load_sparklines()` — all sparkline methods
- [ ] Extract `_load_constraints()` — budgets, health warnings
- [ ] Compose in a shorter `get_dashboard()` orchestrator
- [ ] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
