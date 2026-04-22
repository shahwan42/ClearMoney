---
id: "139"
title: "Dynamic multi-currency foundation"
type: feature
priority: high
status: done
created: 2026-04-22
updated: 2026-04-22
---

## Description

Introduce the first implementation slice for dynamic multi-currency support:
currency registry, per-user active/display currency preferences, header selector,
settings management, and registry-backed currency options in the first set of
editable forms and filters.

This ticket establishes the platform the remaining multi-currency rollout will
build on. It does not yet generalize people balances, dashboard totals,
historical snapshots, or net-worth aggregation.

## Details

- Added a registry-backed `Currency` model and `UserCurrencyPreference` model
- Added a migration that seeds supported currencies and backfills each user's
  active currencies and selected display currency from existing data
- Added shared currency preference helpers for supported currencies, active
  currencies, and selected display currency
- Added settings endpoints and UI for updating active currencies and display
  currency
- Added the top-bar display currency selector
- Replaced the first round of hard-coded `EGP` / `USD` form options in accounts,
  budgets, investments, and reports with registry-backed options
- Updated reports to default to the user's selected display currency when no
  explicit currency filter is supplied

## Acceptance Criteria

- [x] Supported currencies come from a registry, not hard-coded template lists
- [x] Users can persist active currencies and a selected display currency
- [x] Header selector updates the selected display currency
- [x] Account-side editable currency forms support dynamic active currencies
- [x] Existing users are backfilled with valid preferences
- [x] Full test suite passes with the foundation slice in place

## Critical Files

- `backend/auth_app/models.py`
- `backend/auth_app/currency.py`
- `backend/auth_app/migrations/0007_currency_registry_and_preferences.py`
- `backend/core/context_processors.py`
- `backend/clearmoney/settings.py`
- `backend/settings_app/views.py`
- `backend/settings_app/urls.py`
- `backend/settings_app/templates/settings_app/settings.html`
- `backend/templates/components/header.html`
- `backend/accounts/services.py`
- `backend/accounts/templates/accounts/_account_form.html`
- `backend/accounts/templates/accounts/_add_account_form.html`
- `backend/accounts/templates/accounts/_account_edit_form.html`
- `backend/budgets/templates/budgets/budgets.html`
- `backend/investments/templates/investments/investments.html`
- `backend/reports/views.py`
- `backend/reports/templates/reports/reports.html`

## Unit Tests

- `backend/auth_app/tests/test_currency.py`
- `backend/settings_app/tests/test_views.py`
- `backend/accounts/tests/test_services.py`
- `backend/accounts/tests/test_views.py`
- `backend/reports/tests/test_views.py`
- `backend/reports/tests/test_services.py`
- `backend/budgets/tests/test_views.py`
- `backend/investments/tests/test_views.py`

## E2E / Integration Coverage

- Existing-user preference backfill exercised via migration and model/service tests
- Header display-currency persistence covered through authenticated view tests
- Dynamic form-option rendering covered across account, budget, investment, and
  report flows

## Follow-up Tickets

- `#140` Audit and finish registry-backed currency option rollout
- `#141` Complete selected-currency plumbing across remaining entry points
- `#142` onward for generalized balances, summaries, snapshots, and cleanup

## Progress Notes

- 2026-04-22: Started — implementing currency registry, per-user preferences,
  header selector, and registry-backed currency options
- 2026-04-22: Added `Currency` and `UserCurrencyPreference` models, seeded and
  backfilled preferences, added settings management and header selector, and
  replaced initial hard-coded currency options in accounts, budgets,
  investments, and reports
- 2026-04-22: Verified with targeted pytest suites, `python backend/manage.py
  makemigrations --check --dry-run`, and full-suite `pytest -q` with 1522 tests
  passing

