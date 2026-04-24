---
id: "155"
title: "Improve transaction account picker UX with icons and search"
type: improvement
priority: medium
status: pending
created: 2026-04-24
updated: 2026-04-24
---

## Description

Selecting an account while creating an expense or income transaction is still a plain native `<select>`, which gets harder to use as the account list grows. The picker should surface visual identity and support faster lookup.

Current state:
- Full transaction form uses a plain account `<select>` in `backend/transactions/templates/transactions/transaction_new.html`
- Quick entry also uses a plain account `<select>` in `backend/transactions/templates/transactions/_quick_entry.html`
- Account dropdown data from `TransactionService.get_accounts()` does not include icon/institution presentation data today

## Acceptance Criteria

- [ ] Account picker shows an icon or visual avatar for each account option
- [ ] Picker supports searching/filtering accounts by name
- [ ] Full transaction form uses the improved picker
- [ ] Quick-entry form uses the improved picker
- [ ] Existing account validation and submission behavior remain intact
- [ ] Accessibility preserved: keyboard navigation, labels, focus states, and screen-reader compatibility
- [ ] Tests added or updated for the new picker behavior

## Technical Notes

- Existing category combobox implementation in `static/js/category-combobox.js` may be reusable as the base pattern
- Likely need extra dropdown data from accounts/institutions, such as institution icon and fallback avatar behavior
- Keep native-form semantics through a hidden input or equivalent submitted value

## Progress Notes

- 2026-04-24: Created from feature triage. Confirmed current transaction account inputs are plain `<select>` elements with no icon rendering and no search behavior.
