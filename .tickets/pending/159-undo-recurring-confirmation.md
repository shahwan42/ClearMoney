---
id: "159"
title: "Add Undo capability for recurring confirmations"
type: improvement
priority: medium
status: pending
created: 2026-04-26
updated: 2026-04-26
---

## Description

When a user uses "Quick Confirm" or "Confirm All" on the recurring calendar, the items are immediately processed and removed from the list. If a user clicks by mistake, there is currently no easy way to revert this without manually finding and deleting the created transactions and then manually rolling back the `next_due_date` on the recurring rule.

## Acceptance Criteria

- [ ] Users can undo a "Quick Confirm" action within a short grace period (e.g., 5-10 seconds)
- [ ] Users can undo a "Confirm All" action
- [ ] Undoing a confirmation deletes the created transaction(s)
- [ ] Undoing a confirmation reverts the `next_due_date` on the `RecurringRule` to its previous state
- [ ] Undoing a confirmation correctly restores the account balance(s)
- [ ] The UI provides clear feedback when an undo is available and when it has been successfully performed

## Technical Requirements

- [ ] Need a way to track which transaction was created by which confirmation event (e.g., temporary session state or a transaction metadata field)
- [ ] Reverting must be atomic (transaction deletion + rule update)
- [ ] UI pattern: Consider a toast with an "Undo" button or a "Recently Confirmed" section

## Progress Notes

- 2026-04-26: Created following the implementation of detailed confirmation sheet and quick confirm actions.
