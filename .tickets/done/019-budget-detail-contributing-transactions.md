---
id: "019"
title: "Show contributing transactions on budget click"
type: feature
priority: medium
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

When a user clicks on a budget (on the /budgets page), show the list of transactions that contribute to that budget's spending for the current month. Currently budgets show spent/limit/remaining but there's no way to drill into which transactions make up the spent amount.

## Acceptance Criteria

- [x] Clicking a budget card on /budgets navigates to a budget detail view (e.g. /budgets/<id>)
- [x] Detail view shows the budget header: category name, icon, spent / limit, progress bar, status
- [x] Detail view lists all expense transactions matching the budget's category + currency for the current month
- [x] Each transaction row shows: date, note, amount, account name
- [x] Transactions are sorted by date descending (newest first)
- [x] Empty state shown if no transactions yet ("No transactions this month")
- [x] Back navigation to /budgets
- [x] Per-user data isolation (only shows authenticated user's transactions)
- [x] Service-level tests: happy path, empty transactions, month filtering, data isolation
- [x] View tests: GET 200, auth redirect, 404 for other user's budget
- [x] E2E test: click budget → see transactions listed
- [x] Accessible: semantic HTML, keyboard navigable, screen reader friendly

## Technical Notes

- `BudgetService.get_all_with_spending()` already calculates spending via Subquery on Transaction model filtering by `category_id`, `user_id`, `type='expense'`, current month, and `currency`
- New service method needed: `get_budget_transactions(budget_id)` — query Transaction model with same filters, return list
- New view: `budget_detail(request, budget_id)` — GET only
- New URL: `GET /budgets/<uuid:budget_id>/`
- New template: `budgets/budget_detail.html`
- Reuse existing transaction row styling from transactions list if applicable

## Progress Notes

- 2026-03-28: Created — ticket for budget detail view showing contributing transactions
- 2026-03-28: Completed — service method, view, template, budget list link, 6 service tests + 3 view tests + 2 E2E tests all passing (1204 total tests, 7 E2E budget tests)
