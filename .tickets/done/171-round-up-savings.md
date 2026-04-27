---
id: "171"
title: "Round-up savings on expense transactions"
type: feature
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

When a user makes an expense, automatically transfer the round-up amount to a designated savings account. Mirrors Telda's round-up Space feature. Configured per source account.

Example: spend 47 EGP with increment 10 → round-up 3 EGP transferred to savings account automatically.

## Design Decisions

- **Money movement**: real transfer (actual balance moves, not virtual allocation)
- **Config scope**: per source account (each account has its own increment + target)
- **Triggers**: expense transactions only, manually entered only (not recurring)
- **Increment options**: 5, 10, 20, 50, or 100 (user picks one)
- **Already-round amounts**: skip (save 0)
- **Currency**: source and target account must share same currency (enforced at config via dropdown filter)
- **Recording**: real transfer pair with `is_roundup=True` on both legs
- **Linking**: both legs carry `parent_transaction_id = expense.id` for cascade delete
- **Lifecycle**: locked to triggering expense — deleting expense cascades to delete round-up transfer
- **Insufficient balance**: skip round-up silently (expense still goes through)
- **UI**: collapsible "Round-up savings" section on account edit form

## What Was Built

- `Account.roundup_increment` (SmallIntegerField, nullable, choices 5/10/20/50/100)
- `Account.roundup_target_account` (FK to self, SET_NULL)
- `Transaction.is_roundup` (BooleanField, default False)
- `Transaction.parent_transaction` (FK to self, SET_NULL, related_name='roundup_children')
- Migrations: `accounts/0009`, `transactions/0011`
- `TransactionServiceBase._apply_roundup()` — post-create hook for expenses
- `TransactionServiceBase.delete()` — cascade-deletes round-up children on expense delete
- `AccountService.get_roundup_targets()` — filters same-currency, non-credit, non-dormant accounts
- `AccountService.update()` — handles roundup_increment + roundup_target_account_id
- `AccountService._FIELDS` + `AccountSummary` updated with new fields
- `account_edit_form` view passes `roundup_targets` to template
- `account_update` view reads roundup fields from POST
- `_account_edit_form.html` — collapsible round-up section with increment + target dropdowns

## Acceptance Criteria

- [x] Account model has `roundup_increment` and `roundup_target_account_id` fields with migration
- [x] Transaction model has `is_roundup` and `parent_transaction_id` fields with migration
- [x] Account edit form shows "Round-up savings" collapsible section with increment selector + target account dropdown (same-currency accounts only)
- [x] Creating expense on configured account triggers round-up transfer automatically
- [x] Round-up transfer legs are marked `is_roundup=True`
- [x] Round-up legs linked to expense via `parent_transaction_id`
- [x] Already-round amounts skip silently
- [x] Insufficient balance skips silently (expense still created)
- [x] Deleting expense cascades to delete linked round-up transfer
- [x] Recurring auto-created transactions do NOT trigger round-up
- [x] Target account dropdown filtered to same-currency, non-credit, non-dormant accounts
- [x] 10 service tests — all passing
- [ ] E2E test: configure round-up → create expense → verify both balances updated (deferred)

## Progress Notes

- 2026-04-27: Started — Design finalized via interview. Ready for implementation.
- 2026-04-27: Completed — Models, migrations, service logic, UI all implemented. 1691 tests pass, zero lint errors.
