---
id: "165"
title: "Single-entry loans (no account impact)"
type: feature
priority: medium
status: wip
created: 2026-04-27
updated: 2026-04-27
---

## Description

Allow recording loans and repayments without affecting an account balance. Useful for tracking historical/informal loans. Transaction.account becomes nullable; single-entry rows have balance_delta=0 and no account link.

## Acceptance Criteria

- [ ] `Transaction.account` is nullable (additive migration)
- [ ] "Don't affect account balance" checkbox in Record Loan form hides account dropdown, shows currency dropdown
- [ ] Same checkbox in Repayment form
- [ ] `record_loan` and `record_repayment` services accept `account_id=None` + explicit `currency`
- [ ] Person balance (PersonCurrencyBalance) still updated for single-entry loans
- [ ] Single-entry loans excluded from main transaction list
- [ ] "memo" badge on person detail page for transactions without account
- [ ] Service + view tests cover single-entry path

## Progress Notes

- 2026-04-27: Started — implementing nullable account migration, service, view, template changes
- 2026-04-27: Completed — migration applied, 9 new tests (7 service + 2 view), all 1632 tests pass, lint clean
