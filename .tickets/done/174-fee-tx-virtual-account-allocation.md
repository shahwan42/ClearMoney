---
id: "174"
title: "Record fee transactions against same virtual account"
type: feature
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

When a transaction is created/edited with both a fee and a virtual account (pot) selected, the fee transaction should be allocated to the same pot as the parent transaction.

## Acceptance Criteria

- [x] Creating a transaction with fee + VA allocates fee tx to same VA (`-fee_amount`)
- [x] Editing a transaction (fee or VA changes) re-allocates fee tx accordingly
- [x] Removing VA on edit deallocates fee tx from VA
- [x] Removing fee on edit deallocates old fee tx from VA
- [x] Deleting a transaction deallocates fee tx from VA before deletion (VA balance reversed)
- [x] `update_fee_for_transaction` returns `dict | None` (fee tx or None)

## Progress Notes

- 2026-04-27: Started — implementing fee VA allocation across create/edit/delete flows
- 2026-04-27: Completed — 7 new tests, all passing. 1712 total passing, lint clean.
