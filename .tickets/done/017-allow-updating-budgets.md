---
id: "017"
title: "Allow updating budgets"
type: feature
priority: medium
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

Category budgets currently lack edit/update functionality. Users must delete and recreate a budget to change its monthly limit. Add the ability to update an existing budget's `monthly_limit` inline — matching the pattern already used by TotalBudget (which uses `update_or_create`).

## Current State

- **TotalBudget**: Can be updated inline (template lines 43-55, `set_total_budget()` uses `update_or_create`)
- **Budget (per-category)**: Read-only display with only a Delete button (template lines 112-131)
- No `update()` service method, no edit view, no edit URL route, no tests for update

## Acceptance Criteria

- [x] `BudgetService.update()` method allows changing `monthly_limit` for an existing budget
- [x] `update()` validates: budget exists, belongs to user, new limit > 0
- [x] `update()` raises `ValueError` for invalid limit, returns `False` / 404 for missing/wrong-user budget
- [x] POST `/budgets/<uuid:budget_id>/edit` view accepts new `monthly_limit`
- [x] Budget card in UI has an inline edit affordance (e.g., tap the limit to edit, or an Edit button that reveals an input)
- [x] After update, page redirects back to `/budgets` showing the updated limit
- [x] Service-layer unit tests: happy path, invalid limit, wrong user (isolation), non-existent budget
- [x] View-layer unit tests: POST success (302), validation error (400), other user's budget (404)
- [x] E2E test: edit a budget's limit and verify the new limit displays correctly
- [x] Accessibility: form input has `<label>` or `aria-label`, keyboard navigable

## Key Files

- `backend/budgets/services.py` — add `update()` method
- `backend/budgets/views.py` — add `budget_edit` view
- `backend/budgets/urls.py` — add edit route
- `backend/budgets/templates/budgets/budgets.html` — add edit UI to budget cards
- `backend/budgets/tests/test_services.py` — add `TestBudgetUpdate`
- `backend/budgets/tests/test_views.py` — add `TestBudgetEdit`
- `e2e/tests/test_budgets.py` — add edit E2E test

## Progress Notes

- 2026-03-28: Ticket created — explored existing budget CRUD, confirmed update is missing
- 2026-03-28: Implemented — service update(), view budget_edit, inline edit form in template, 10 unit tests + 1 E2E test, all passing (1204 unit, 157 E2E)
- 2026-03-28: Completed — all acceptance criteria met, committed as feat: allow updating budget monthly limits inline
