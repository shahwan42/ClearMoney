---
id: "137"
title: "Fix transfer delete balance direction bug"
type: bug
priority: high
status: done
created: 2026-04-20
updated: 2026-04-20
---

## Description

Deleting the credit leg (destination side) of a transfer incorrectly reversed
both account balances in the wrong direction. The delete function hardcoded
`+amount` on the deleted transaction's account and `-amount` on the linked
account, which is correct only when deleting the debit leg. When the credit
leg is deleted, both directions are inverted, corrupting both balances.

## Acceptance Criteria

- [x] Deleting either leg of a transfer correctly reverses both balances
- [x] Test covering credit-leg deletion added

## Progress Notes

- 2026-04-20: Started — Diagnosed from production backup showing ±100, ±4000, ±25500 drifts across 5 accounts caused by this bug
- 2026-04-20: Completed — Fixed `delete()` in `transactions/services/crud.py` to use `balance_delta` (already available) instead of hardcoded direction. `current_balance -= balance_delta` correctly reverses any leg: debit (delta<0 → balance goes up) or credit (delta>0 → balance goes down). Added `test_delete_credit_leg_reverses_both_accounts_correctly`. All 1534 tests pass.
