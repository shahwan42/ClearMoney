---
id: "523"
title: "Fix loan repayment delete/update leaving stale account balance"
type: bug
priority: high
status: done
created: 2026-05-02
updated: 2026-05-02
---

## Description

`TransactionService.delete()` and `update()` use `_balance_delta(type, amount)` to
compute the reverse/adjustment for account balance. This helper returns `Decimal(0)`
for `loan_repayment`, `loan_in`, and `loan_out` types — so deleting or editing those
transactions silently leaves the account `current_balance` wrong.

Reported via HSBC Checking EGP account: balance 20,000 short after a
`loan_repayment` was deleted and recreated as an `expense`.

## Affected User Journeys

- CP-2 (Core Financial Loop): balance updates are corrupted for loan transactions.
- J-2 (Financial Loop): any loan repayment delete/edit silently corrupts balance.

## Acceptance Criteria

- [x] `delete()` correctly restores account balance for `loan_repayment`/`loan_in`/`loan_out`
- [x] `update()` correctly adjusts account balance for amount changes on loan types
- [x] Tests added for delete and update on loan_repayment
- [ ] HSBC Checking EGP current_balance corrected to 51,808.27 (via Balance Check UI)
- [x] `make test` green (1847 passed), `make lint` zero errors (pre-existing unrelated issue)

## Progress Notes

- 2026-05-02: Started — root cause confirmed via DB backup analysis. initial_balance + sum(balance_deltas) = 51,808.27 but current_balance = 31,808.27 (20,000 short). Fix: use stored balance_delta in delete()/update() instead of _balance_delta().
- 2026-05-02: Completed — delete() now uses -Decimal(str(tx["balance_delta"])) instead of -_balance_delta(type, amount); update() uses stored balance_delta for old_delta on loan types. 3 new tests added. Data fix via Balance Check UI (Balance Correction feature).
