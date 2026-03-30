---
id: "020"
title: "Recurring rules money movement + fee"
type: feature
priority: medium
status: done
created: 2026-03-29
updated: 2026-03-30
---

## Description

Extend recurring rules to support "Money Movement" (same-currency transfers between accounts) with an optional fee field. Currently recurring rules only support expense and income types.

## Acceptance Criteria

- [x] Form has a third "Transfer" radio option alongside Expense/Income
- [x] When Transfer selected: destination account dropdown and fee input appear, category hides
- [x] Transfer recurring rules store counter_account_id and fee_amount in template_transaction JSONB
- [x] Executing a transfer rule calls TransactionService.create_transfer() with proper arguments
- [x] Rule list displays transfer rules with source → destination and fee info
- [x] Pending confirmations section handles transfer rules correctly
- [x] Service tests cover transfer execution, fee handling, missing counter_account
- [x] View tests cover transfer creation, validation errors
- [x] E2E test covers creating a transfer recurring rule via UI

## Progress Notes

- 2026-03-29: Started — Explored codebase, planned implementation across service/view/template layers
- 2026-03-30: Completed — 14 new tests (9 service + 5 view), E2E tests written, all 1225 unit tests pass, lint clean
