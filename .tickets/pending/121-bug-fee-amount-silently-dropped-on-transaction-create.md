---
id: "121"
title: "Bug: Fee amount silently dropped when creating transaction — balance not updated correctly"
type: bug
priority: high
status: pending
created: 2026-04-17
updated: 2026-04-17
---

## Description

When creating an expense transaction with a `fee_amount` via the service layer (and likely via the UI form as well), the fee is **silently dropped** — stored as `None` on the transaction and the account balance is reduced by only `amount`, not `amount + fee`.

**Observed:**
- TX created with `amount=1000`, `fee="50.00"` 
- Stored in DB: `fee_amount=None`, `balance_delta=-1000`
- Account balance reduced by 1000, not 1050
- Fee amount EGP 50 disappears entirely

**Expected:**
- Fee stored in `tx.fee_amount = 50.00`
- Balance reduced by `amount + fee = 1050`
- OR: fee creates a separate linked transaction (if that's the design intent — but must be documented and visible)

## Root Cause (Suspected)

The `TransactionService.create()` method receives `data` as a dict. The `fee` key in the dict may not be mapped to `fee_amount` in the model, or the `create_fee_for_transaction()` method is not being called from the `create()` path.

Confirmed via DB query after creating TX with fee:
```
type=expense  note=Restaurant with service charge  amt=1000.00  fee=None  balance_delta=-1000.00
```

`create_fee_for_transaction()` exists in `crud.py` but appears to not be invoked automatically by `create()`.

## Steps to Reproduce

1. Open the Quick Entry form
2. Click "More options" to expand fee field
3. Enter Amount: 1000, Fee: 50
4. Submit
5. Check account balance — reduced by 1000 only (expected: 1050)
6. Open transaction detail — fee not shown

## Impact

- Financial data integrity issue: fees not tracked
- Balance drift: account balance doesn't match reality when fees paid
- Undermines the core financial tracking purpose

## Acceptance Criteria

- [ ] Creating a transaction with `fee_amount=50` reduces account balance by `amount + fee`
- [ ] `tx.fee_amount` is stored correctly in the database
- [ ] Transaction detail view shows the fee amount
- [ ] Balance delta = -(amount + fee) for expense, or +(amount - fee) for income
- [ ] Service-layer test: `test_create_expense_with_fee_deducts_amount_plus_fee`

## Progress Notes

- 2026-04-17: Filed during manual QA session (ticket #117). Confirmed via DB: `fee_amount=None` after service call with `fee="50.00"` in data dict.
