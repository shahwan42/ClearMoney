---
id: "175"
title: "Pending transaction settlement"
type: feature
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Some transactions (online purchases, hotel holds, foreign currency) post with an estimated amount and settle a few days later with the real final amount. Users need to mark transactions as pending and later settle them with the actual amount, seeing the difference.

## Acceptance Criteria

- [x] Transaction can be marked as pending via toggle in "More options" on create form
- [x] Pending transactions show amber badge in list row metadata + tilde on amount
- [x] Pending transactions show amber callout in detail sheet with original amount
- [x] "Settle" button opens a bottom sheet with final amount input and live diff preview
- [x] Settling updates `amount`, flips `is_pending=False`, preserves `original_amount`
- [x] Balance delta recalculated on settle
- [x] Budgets/reports use final settled amount (no special logic needed — use `amount`)
- [x] `original_amount` always stored when created as pending (never mutated after)
- [x] All fields editable while pending (standard edit form unchanged)
- [x] Deletable like any transaction (balance reverses via existing delete path)

## Progress Notes

- 2026-04-27: Started — Design finalised via grill-me + design-an-interface sessions.
- 2026-04-27: Completed — Migration (0012), model fields, service settle(), 10 tests, views, templates. 1722 tests pass, zero lint/mypy errors.
