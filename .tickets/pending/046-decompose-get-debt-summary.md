---
id: "046"
title: "Decompose get_debt_summary (100+ lines)"
type: refactor
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

`get_debt_summary()` in `people/services.py` (lines ~399-501) is 100+ lines with per-currency tallies, nested loops over transactions, and projected payoff calculations embedded inline. Break into focused sub-functions.

## Acceptance Criteria

- [ ] Extract `_compute_currency_breakdown(transactions)` — per-currency stats
- [ ] Extract `_compute_aggregate_progress(breakdown)` — progress metrics
- [ ] Extract `_compute_projected_payoff(repayment_dates, remaining, total_repaid)` — date calculation
- [ ] Compose in a shorter `get_debt_summary()` orchestrator
- [ ] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
