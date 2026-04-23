---
id: "148"
title: "Dynamic budgets and total budgets"
type: feature
priority: medium
status: done
created: 2026-04-22
updated: 2026-04-23
---

## Description

Generalize budget and total-budget flows so they work with any active currency
and no longer rely on EGP-oriented defaults or assumptions.

## Details

- Finish replacing budget-side currency assumptions beyond the initial `#139`
  form option rollout
- Ensure total budgets can be created, queried, and rendered for arbitrary
  active currencies
- Align budget widgets and detail views with selected-currency behavior where
  appropriate
- Preserve per-currency uniqueness and exact-currency math

## Acceptance Criteria

- [x] Budgets can be created and managed in any active currency
- [x] Total budgets work for any active currency
- [x] Budget views no longer treat `EGP` as a special default
- [x] Budget widgets remain consistent with selected-currency rules

## Critical Files

- `backend/budgets/models.py`
- `backend/budgets/services.py`
- `backend/budgets/views.py`
- `backend/budgets/templates/budgets/budgets.html`
- `backend/budgets/templates/budgets/_total_budget_card.html`
- `backend/dashboard/templates/dashboard/_budgets.html`

## Unit Tests

- Budget CRUD in a third currency
- Total-budget CRUD and lookup in a third currency
- Inactive currency rejection for budget flows

## E2E Tests

- Create and edit a total budget in `EUR`
- Budget list and detail views render `EUR`
- Dashboard budget widgets follow selected-currency behavior

## Dependencies

- Depends on `#140`
- Depends on `#141`

## Progress Notes

- 2026-04-22: Created for budget-side multi-currency completion
- 2026-04-23: Implemented multi-currency total budgets, generalized models/views, and added tests.
