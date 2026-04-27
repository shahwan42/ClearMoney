---
id: "175"
title: "Pending transaction settlement"
type: feature
priority: medium
status: wip
created: 2026-04-27
updated: 2026-04-27
---

## Description

Some transactions (online purchases, hotel holds, foreign currency) post with an estimated amount and settle a few days later with the real final amount. Users need to mark transactions as pending and later settle them with the actual amount, seeing the difference.

## Acceptance Criteria

- [ ] Transaction can be marked as pending via toggle in "More options" on create form
- [ ] Pending transactions show amber badge in list row metadata + tilde on amount
- [ ] Pending transactions show amber callout in detail sheet with original amount
- [ ] "Settle" button opens a bottom sheet with final amount input and live diff preview
- [ ] Settling updates `amount`, flips `is_pending=False`, preserves `original_amount`
- [ ] Balance delta recalculated on settle
- [ ] Budgets/reports use final settled amount
- [ ] `original_amount` always stored when created as pending (never mutated after)
- [ ] All fields editable while pending
- [ ] Deletable like any transaction (balance reverses)

## Progress Notes

- 2026-04-27: Started — Design finalised via grill-me + design-an-interface sessions. Implementing migration → service TDD → views → templates.
