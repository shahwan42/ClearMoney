---
id: "046"
title: "Decompose get_debt_summary (100+ lines)"
type: refactor
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-15
---

## Description

`get_debt_summary()` in `people/services.py` (lines ~399-501) is 100+ lines with per-currency tallies, nested loops over transactions, and projected payoff calculations embedded inline. Break into focused sub-functions.

## Acceptance Criteria

- [x] Extract `_compute_currency_breakdown(transactions, person)` — per-currency stats
- [x] Extract `_compute_aggregate_progress(total_lent, total_borrowed, total_repaid)` — progress metrics
- [x] Extract `_compute_projected_payoff(repayment_dates, remaining, total_repaid)` — date calculation
- [x] Compose in a shorter `get_debt_summary()` orchestrator
- [x] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
- 2026-04-15: Refactored — extracted three private sub-functions, `get_debt_summary` now delegates to them. All 1309 tests pass, ruff/mypy/contracts clean.
