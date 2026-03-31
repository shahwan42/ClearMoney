---
id: "092"
title: "Inline form validation"
type: improvement
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

No real-time validation exists on any form — errors only appear after server-side submission. Add client-side inline validation with `aria-invalid` states and field-specific error messages.

## Acceptance Criteria

- [ ] Amount fields: validate > 0 on blur, show "Amount must be greater than 0"
- [ ] Required fields: validate non-empty on blur, show "This field is required"
- [ ] Date fields: validate not in future on blur (where applicable)
- [ ] Name/note fields: show character count near maxlength (e.g., "95/100")
- [ ] `aria-invalid="true"` set on invalid fields
- [ ] `aria-describedby` links field to its error message element
- [ ] Error messages use `role="alert"` for screen reader announcement
- [ ] Visual: red border + error text below field (consistent with category-combobox pattern)
- [ ] Does not block submission — server validation remains authoritative
- [ ] E2E test for validation appearing on blur, clearing on valid input

## Technical Notes

- Reuse pattern from `static/js/category-combobox.js:335-343` (inline error display)
- New JS module: `static/js/form-validation.js` with `data-validate` attributes
- `data-validate="required"`, `data-validate="min:0.01"`, `data-validate="maxlength:100"`
- Progressive enhancement: works without JS (server validation still catches errors)
- Apply to: transaction forms, account form, budget form, people form, recurring form

## Progress Notes

- 2026-03-31: Created — addresses #1 UX friction point across all forms
