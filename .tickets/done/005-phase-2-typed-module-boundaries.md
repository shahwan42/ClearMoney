---
id: "005"
title: "Phase 2 — Typed contracts at module boundaries"
type: improvement
priority: medium
status: done
created: 2026-03-27
updated: 2026-03-27
---

## Description

Replace `dict[str, Any]` returns with typed dataclasses on the 4 cross-module service methods:
- `AccountService.get_all()` → `list[AccountSummary]`
- `AccountService.get_for_dropdown()` → `list[AccountDropdownItem]`
- `BudgetService.get_all_with_spending()` → `list[BudgetWithSpending]`
- `RecurringService.get_due_pending()` → `list[RecurringRulePending]`

This makes module boundaries type-safe and enables mypy to catch cross-module data errors.

## Acceptance Criteria

- [x] All 4 service methods return typed dataclasses (not dicts)
- [x] All cross-module callers updated to use attribute access (`.field` not `["field"]`)
- [x] Same-module code (views, tests) updated similarly
- [x] mypy passes with zero errors
- [x] All 1157 tests pass
- [x] Django templates render correctly (no changes needed)
- [x] Manual QA: budgets, recurring, push endpoints work

## Progress Notes

- 2026-03-27: Started — Created ticket, beginning Step 1 (accounts/types.py)
- 2026-03-27: Completed — All 4 service methods typed, all callers updated, mypy passes, formatted and ready for testing
- 2026-03-27: DONE — Fixed 11 remaining mypy errors (load_health_warnings Sequence variance, UUID conversions, unused type:ignore). All 1157 tests passing, zero lint errors. Ready for production.
