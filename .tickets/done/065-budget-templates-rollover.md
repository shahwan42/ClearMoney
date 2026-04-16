---
id: "065"
title: "Budget templates and rollover"
type: feature
priority: medium
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

Add "copy last month's budgets" one-click action and optional rollover of unspent budget amounts to the next month.

## Acceptance Criteria

- [ ] "Copy last month" button on budgets page — creates budgets matching previous month's active budgets
- [ ] Skip categories that already have a budget for current month (no duplicates)
- [ ] Optional rollover toggle per budget: unspent amount carries to next month
- [ ] New field on Budget: `rollover_enabled` (Boolean, default False)
- [ ] Rollover logic: `effective_limit = monthly_limit + max(0, last_month_remaining)`
- [ ] Rollover cap: configurable max carryover (prevent unlimited accumulation)
- [ ] Budget history: show how limits changed over time (optional)
- [ ] Service-layer tests for copy, rollover calculation, duplicate handling
- [ ] E2E test for copy action → verify budgets created with correct limits

## Technical Notes

- Additive migration: `rollover_enabled` Boolean field
- `get_all_with_spending()` already computes `remaining` — extend to check previous month
- "Copy last month" is a single POST endpoint that calls `create()` in a loop
- Unique constraint `(user_id, category_id, currency)` prevents duplicates naturally

## Progress Notes

- 2026-03-31: Created — planned as Tier 2 feature recommendation
