---
id: "085"
title: "Bulk edit transactions"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Select multiple transactions and batch-apply changes: re-categorize, add tags, or delete. Currently only individual edit/delete exists.

## Acceptance Criteria

- [ ] Checkbox selection on transaction list (toggle "select mode")
- [ ] "Select all visible" option
- [ ] Action bar: "Change category", "Delete selected" (with confirmation)
- [ ] Batch category change updates all selected transactions atomically
- [ ] Batch delete with balance recalculation for affected accounts
- [ ] Count indicator: "3 selected"
- [ ] Service-layer tests for batch update/delete with balance integrity
- [ ] E2E test for selecting transactions → batch category change → verify updates

## Technical Notes

- New service method: `TransactionService.bulk_update_category(tx_ids, category_id)`
- New service method: `TransactionService.bulk_delete(tx_ids)` with atomic balance reversal
- HTMX: checkbox state managed client-side, action POSTs list of IDs
- Must maintain balance atomicity — use `transaction.atomic()` with `F()` expressions
- Consider max selection limit (50?) to prevent accidental mass operations

## Progress Notes

- 2026-03-31: Created — addresses missing bulk operations on transaction list
