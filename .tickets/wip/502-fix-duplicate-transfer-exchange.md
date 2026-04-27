---
id: "502"
title: "Fix duplicate transfer/exchange transaction"
type: bug
priority: medium
status: wip
created: 2026-04-27
updated: 2026-04-27
---

## Description

Duplicating a transfer or exchange transaction sends to `/transactions/new?dup=<id>`, which only handles expense/income types. Transfer/exchange types fall back to "expense" — wrong form, missing counter_account_id and exchange fields.

## Acceptance Criteria

- [ ] Duplicating a transfer opens `/transfer/new` pre-filled with source, dest, amount, note
- [ ] Duplicating an exchange opens `/transfer/new` pre-filled with source, dest, amount, rate, counter_amount, note
- [ ] Date defaults to today in both cases
- [ ] `updateTransferMode()` called on load to show correct fields

## Progress Notes

- 2026-04-27: Started — redirecting transfer/exchange dup to transfer_new_unified, adding prefill support
- 2026-04-27: Completed — 1725 tests pass, 0 lint errors. 3 new tests added.
