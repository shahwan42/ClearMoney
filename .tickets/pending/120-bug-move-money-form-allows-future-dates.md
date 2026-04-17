---
id: "120"
title: "Bug: Move Money form date input has no max constraint — allows future dates"
type: bug
priority: medium
status: pending
created: 2026-04-17
updated: 2026-04-17
---

## Description

The **Move Money** quick-entry form (Transfer/Exchange) has a `date` input with **no `max` attribute**, allowing users to schedule transfers on future dates. The Transaction (expense/income) form correctly sets `max="{{ today|date:'Y-m-d' }}"`.

**Observed:** Move Money `date` input: `max=""` (no constraint)  
**Expected:** `max="2026-04-17"` (today's date, same as Transaction form)

## Root Cause

The `date` field in the Move Money form template (likely `transactions/templates/transactions/quick_move_form.html` or similar) is missing the `max` attribute that exists on the Transaction quick entry form.

Verified via JS:
```js
document.querySelector('#move-money-form input[name="date"]').max  // ""
```

Per QA Guidelines (Section 6):
> Date inputs: `max="{{ today|date:'Y-m-d' }}"` to prevent future dates

## Steps to Reproduce

1. Open the Quick Entry bottom sheet
2. Click "Move Money" tab
3. Inspect the Date field — no future-date restriction
4. Enter a date 10 years in the future → form submits without error

## Acceptance Criteria

- [ ] Move Money form `date` input has `max="{{ today|date:'Y-m-d' }}"` attribute
- [ ] Attempting to submit with a future date shows a validation error
- [ ] Consistent behavior with the Transaction form

## Progress Notes

- 2026-04-17: Filed during manual QA session (ticket #117). Verified via form inspection JS.
