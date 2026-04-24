---
id: "156"
title: "Rank transaction account choices by usage within selected transaction type"
type: improvement
priority: medium
status: pending
created: 2026-04-24
updated: 2026-04-24
---

## Description

Account ordering is partially implemented already, but it is global rather than transaction-type aware. The feature request asks for account ranking by most-used account for the active transaction type.

Current state:
- `TransactionService.get_accounts()` orders accounts by total transaction count, then `display_order`, then `name`
- `get_smart_defaults()` only preselects the last used account; it does not compute per-type account ranking
- Category defaults are already transaction-type aware, so account ranking is the remaining gap

## Acceptance Criteria

- [ ] Account ranking uses usage counts filtered by the active transaction type
- [ ] Expense and income forms each rank accounts using their own history
- [ ] Deterministic fallback ordering remains in place after usage score ties
- [ ] Full transaction form uses the type-aware ordering
- [ ] Quick-entry form uses the type-aware ordering
- [ ] Behavior is user-scoped; one user's usage does not affect another's ordering
- [ ] Tests cover ranking by transaction type and isolation

## Technical Notes

- This is a refinement of completed ticket `132`, not a brand-new ordering feature
- Current implementation in `backend/transactions/services/helpers.py` counts all transactions, including non-expense/income activity
- Decide whether transfer/exchange forms should keep global ordering or gain their own type-specific ranking separately

## Progress Notes

- 2026-04-24: Created from feature triage. Confirmed current ordering is usage-based but global, so the "most used per transaction type" part is not implemented yet.
