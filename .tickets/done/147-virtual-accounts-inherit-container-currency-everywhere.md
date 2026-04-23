---
id: "147"
title: "Virtual accounts inherit container currency everywhere"
type: improvement
priority: medium
status: done
created: 2026-04-22
updated: 2026-04-23
---

## Description

Virtual accounts should remain currency-less at the model level and always
inherit the currency of their linked container account in display, summaries,
and selected-currency filtering.

## Details

- Audit virtual-account read paths and widgets for direct currency assumptions
- Ensure balance and target formatting use the linked account currency
- Make selected-currency inclusion and exclusion depend on the linked account
  currency
- Define safe behavior for unlinked virtual accounts

## Acceptance Criteria

- [x] Linked virtual accounts display in their container account currency
- [x] Virtual-account summaries participate correctly in selected-currency views
- [x] No virtual-account path hard-codes `EGP`
- [x] Unlinked virtual accounts have a safe, explicit fallback state

## Critical Files

- `backend/virtual_accounts/models.py`
- `backend/virtual_accounts/services.py`
- `backend/virtual_accounts/views.py`
- `backend/dashboard/templates/dashboard/_virtual_accounts.html`
- `backend/accounts/templates/accounts/account_detail.html`

## Unit Tests

- Linked virtual-account currency inheritance
- Unlinked virtual-account fallback behavior
- Selected-currency inclusion/exclusion for virtual accounts

## E2E Tests

- Virtual account under a non-USD/EGP account renders correctly
- Dashboard and account detail views use inherited currency formatting

## Dependencies

- Depends on `#141`
- Depends on `#145`

## Progress Notes

- 2026-04-22: Created for virtual-account currency normalization
- 2026-04-23: Started — auditing service, dashboard, account-detail, and transaction dropdown paths for linked-account currency inheritance
- 2026-04-23: Completed — added inherited-currency payloads for virtual accounts, updated list/detail/dashboard/transaction goal rendering, added explicit unlinked fallbacks, and verified with `make test`, `make lint`, and `make test-e2e`
