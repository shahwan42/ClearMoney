---
id: "140"
title: "Complete registry-backed currency option rollout"
type: improvement
priority: high
status: pending
created: 2026-04-22
updated: 2026-04-22
---

## Description

Ticket `#139` established the currency registry and replaced the first set of
hard-coded `EGP` / `USD` inputs. This ticket finishes the audit and rollout
across the remaining editable and filterable surfaces so no product path
depends on a fixed two-currency option list.

## Details

- Audit templates, forms, view defaults, and validation paths for remaining
  literal `EGP` / `USD` option lists or hidden defaults
- Standardize all user-selectable currency inputs on active-currency-driven
  option sources
- Keep server-owned currency derivation where account currency is authoritative
- Remove silent `EGP` fallbacks that override user intent in form handling
- Document any intentional exceptions that remain legacy FX-only behavior

## Acceptance Criteria

- [ ] No editable currency selector is hard-coded to `EGP` / `USD`
- [ ] No hidden form field silently forces `EGP` when user choice is expected
- [ ] Account-adjacent and settings-adjacent forms support a third active currency
- [ ] Validation rejects inactive currencies for user-selectable inputs
- [ ] Remaining fixed-currency paths are either removed or explicitly documented

## Critical Files

- `backend/accounts/services.py`
- `backend/accounts/templates/accounts/_account_form.html`
- `backend/accounts/templates/accounts/_add_account_form.html`
- `backend/accounts/templates/accounts/_account_edit_form.html`
- `backend/budgets/views.py`
- `backend/budgets/templates/budgets/budgets.html`
- `backend/investments/templates/investments/investments.html`
- `backend/reports/views.py`
- `backend/reports/templates/reports/reports.html`
- `backend/settings_app/views.py`

## Unit Tests

- Account validation accepts active non-USD/EGP currencies
- User-selectable forms reject inactive currencies
- View defaults prefer active or selected currencies instead of hard-coded values
- Regression coverage for any remaining legacy FX-only branches

## E2E Tests

- Create and edit an account in `EUR`
- Create a budget and investment in `EUR`
- Navigate forms that previously defaulted to `EGP` and confirm they now honor
  active currencies or user selection

## Dependencies

- Depends on `#139`

## Progress Notes

- 2026-04-22: Created after `#139` to finish the registry-backed option rollout

