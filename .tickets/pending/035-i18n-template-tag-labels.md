---
id: "035"
title: "i18n — template tags (account type + transaction type labels)"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Wrap the hardcoded account type and transaction type label dictionaries in `core/templatetags/money.py` with `gettext_lazy()` so they display in the user's language. Also fix the "Credit Limit" vs "Credit Line" discrepancy between services and template tags.

## Acceptance Criteria

- [ ] Account type labels wrapped with `gettext_lazy()`: Savings, Current, Prepaid, Cash, Credit Card, Credit Limit
- [ ] Transaction type labels wrapped with `gettext_lazy()`: Expense, Income, Transfer, Exchange, Loan Given, Loan Received, Loan Repayment
- [ ] "Credit Limit" / "Credit Line" discrepancy resolved (use consistent label)
- [ ] Arabic translations added to `.po` file
- [ ] Labels display in Arabic when user language is Arabic
- [ ] `make test` passes, `make lint` clean

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/core/templatetags/money.py`
- `backend/accounts/services.py` (ACCOUNT_TYPE_LABELS dict)
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for label dictionaries in template tags
