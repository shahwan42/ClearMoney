---
id: "170"
title: "Transfer edit: allow changing source and destination accounts"
type: feature
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Currently editing a transfer only allows changing amount, fee, date, and note.
Users cannot fix an incorrect source or destination account without deleting and recreating the transfer.

## Acceptance Criteria

- [x] Transfer edit form shows "From" (source) and "To" (destination) account dropdowns
- [x] Dropdowns pre-select current source/destination, normalized via balance_delta
- [x] On save, source/destination changes update both legs atomically (account_id, counter_account_id, balances)
- [x] Fee transaction moves to new source account atomically if source changes
- [x] Currency mismatch between new source/dest is rejected with clear error
- [x] Cannot set source == destination (rejected with error)
- [x] Dormant/deleted accounts excluded from dropdowns (via svc.get_accounts())
- [x] All balance updates use F() expressions inside transaction.atomic()

## Progress Notes

- 2026-04-27: Started — grill-me complete, design decisions locked. Writing RED tests first.
- 2026-04-27: Completed — service updated (update_transfer gains source_id/dest_id params, undo+apply balance strategy), view passes accounts to edit form, template adds From/To dropdowns. 20 tests added (16 service + 4 view). 1681 passing, lint clean.
