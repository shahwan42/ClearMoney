---
id: "092"
title: "Inline form validation"
type: improvement
priority: high
status: completed
created: 2026-03-31
updated: 2026-04-18
---

## Description

No real-time validation exists on any form — errors only appear after server-side submission. Add client-side inline validation with `aria-invalid` states and field-specific error messages.

## Acceptance Criteria

- [x] Amount fields: validate > 0 on blur, show "Amount must be greater than 0"
- [x] Required fields: validate non-empty on blur, show "This field is required"
- [x] Date fields: validate not in future on blur (where applicable)
- [x] Name/note fields: show character count near maxlength (e.g., "95/100")
- [x] `aria-invalid="true"` set on invalid fields
- [x] `aria-describedby` links field to its error message element
- [x] Error messages use `role="alert"` for screen reader announcement
- [x] Visual: red border + error text below field (consistent with category-combobox pattern)
- [x] Does not block submission — server validation remains authoritative
- [x] E2E test for validation appearing on blur, clearing on valid input

## Technical Notes

- Reuse pattern from `static/js/category-combobox.js:335-343` (inline error display)
- New JS module: `static/js/form-validation.js` with `data-validate` attributes
- `data-validate="required"`, `data-validate="min:0.01"`, `data-validate="maxlength:100"`
- Progressive enhancement: works without JS (server validation still catches errors)
- Apply to: transaction forms, account form, budget form, people form, recurring form

## Progress Notes

- 2026-03-31: Created — addresses #1 UX friction point across all forms
- 2026-04-18: Implemented — form-validation.js module, applied to all major forms, E2E tests added

## Implementation Summary

### Files Created
- `static/js/form-validation.js` — Core validation module with blur handlers, error display, character counts

### Files Modified
- `backend/templates/base.html` — Added form-validation.js script
- `backend/transactions/templates/transactions/transaction_new.html` — Amount, required, note, fee, date validation
- `backend/accounts/templates/accounts/_account_form.html` — Balance, credit limit validation
- `backend/accounts/templates/accounts/_add_account_form.html` — Name, balance, credit limit validation
- `backend/budgets/templates/budgets/budgets.html` — Monthly limit validation (3 forms)
- `backend/people/templates/people/people.html` — Name required + maxlength
- `backend/recurring/templates/recurring/_form.html` — Amount, account, fee, note, date validation
- `backend/virtual_accounts/templates/virtual_accounts/virtual_accounts.html` — Name, targets, account, icon validation
- `backend/transactions/templates/transactions/_transfer_form.html` — Source, dest, amount, fee, note, date validation
- `e2e/tests/test_form_validation.py` — 20+ E2E tests for validation behavior

### Validation Rules Implemented
- `required` — "This field is required"
- `min:X` — "Amount must be greater than 0"
- `maxlength:X` — Character count display with warning at 90%
- `date:not-future` — "Date cannot be in the future"

### Accessibility Features
- `aria-invalid="true"` on invalid fields
- `aria-describedby` linking fields to error messages
- `role="alert"` on error containers for screen reader announcement
- Red border + error text visual pattern

### Test Coverage
- Amount validation (min value)
- Required field validation
- Character count display
- Future date rejection
- Error clearing on valid input
- aria-describedby linkage
- role="alert" verification
- Form submission not blocked
