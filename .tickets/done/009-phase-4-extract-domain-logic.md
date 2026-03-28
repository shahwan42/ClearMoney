---
id: "009"
title: "Phase 4: Extract domain logic from dashboard to leaf services"
type: improvement
priority: medium
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

Extract domain-specific logic from dashboard submodules into owning leaf services, making dashboard a pure aggregator. Part of the modular monolith architecture plan (Phase 4).

## Acceptance Criteria

- [x] Net worth computation moved to accounts/services.py
- [x] Budget spending calculation — dashboard delegates to BudgetService.get_all_with_spending()
- [x] Spending velocity — kept in dashboard (reports is an aggregator per import-linter contract)
- [x] Recent transactions moved to transactions/services/activity.py
- [x] Streak tracking moved to transactions/services/activity.py
- [x] Dashboard delegates to leaf services (no domain logic)
- [x] All existing tests pass (1157 passed)
- [x] import-linter passes (2 contracts kept, 0 broken)

## Progress Notes

- 2026-03-28: Started — Reading dashboard submodules to understand extraction scope
- 2026-03-28: Completed — 4 extractions done: net worth → accounts, budgets → BudgetService, recent txns + streak → transactions. Spending velocity kept in dashboard because reports is an aggregator (independence contract). All 1157 tests pass, lint clean, import-linter clean.
