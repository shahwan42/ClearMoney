---
id: "121"
title: "Bug: Fee amount silently dropped when creating transaction — balance not updated correctly"
type: bug
priority: high
status: done
created: 2026-04-17
updated: 2026-04-18
---

## Description

When creating an expense transaction with a `fee_amount` via the service layer (and likely via the UI form as well), the fee is **silently dropped** — stored as `None` on the transaction and the account balance is reduced by only `amount`, not `amount + fee`.

**Confirmed via manual QA:** The view layer DOES create a separate linked fee transaction correctly (via `create_fee_for_transaction`). The `fee_amount` column on the parent transaction model is always NULL — it was designed for an older "embedded fee" approach that was replaced by the "separate fee transaction" approach.

**Design decision:** Remove `fee_amount` and `fee_account_id` from the Transaction model entirely. The fee is always represented as a separate linked expense transaction. Having both would create a dual-source-of-truth risk.

## Acceptance Criteria

- [ ] Fee creates a separate linked transaction (`type=expense`, `note="Transaction fee"`)
- [ ] Fee transaction's `linked_transaction_id` points to the parent transaction
- [ ] Account balance reduced by `amount + fee` (net effect of both transactions)
- [ ] Transaction detail view shows linked fee amount
- [ ] Deleting parent transaction also deletes linked fee transaction and reverses its balance impact
- [ ] `fee_amount` and `fee_account_id` columns removed from Transaction model (no dual-source-of-truth)
- [ ] Service test: `test_create_expense_with_fee_deducts_amount_plus_fee` (verifies total balance impact via the two-transaction pattern)
- [ ] All existing tests pass after removing the redundant fields

## Progress Notes

- 2026-04-17: Filed during manual QA session (ticket #117). Confirmed via DB: `fee_amount=None` after service call with `fee="50.00"` in data dict.
- 2026-04-17: Started — Confirmed view layer works. Design decision: remove `fee_amount`/`fee_account_id` from model. Show fee in detail view. Add missing tests.
- 2026-04-18: Completed — Dropped `fee_amount`/`fee_account_id` columns via migration 0008; purged from crud.py, helpers.py, transfers.py; fee shown in detail sheet; added `test_create_expense_with_fee_deducts_amount_plus_fee`; 1469 tests passing.
