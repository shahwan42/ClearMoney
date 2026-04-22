id: "102"
title: "Transaction detail enhancements"
type: improvement
priority: low
status: done
created: 2026-03-31
updated: 2026-04-22
---

## Description

Transaction detail bottom sheet is missing several useful actions and indicators. Add recurring rule indicator, "Duplicate" action, and replace browser `confirm()` with app-native delete confirmation.

## Acceptance Criteria

- [x] Recurring indicator: if transaction has `recurring_rule_id`, show "Recurring: [rule name]" badge
- [x] "Duplicate" button: creates new transaction pre-filled with same data (amount, category, account, note) and today's date
- [x] Delete confirmation: replace `hx-confirm` browser dialog with app-native inline confirmation (red "Confirm Delete" button that appears on first tap)
- [x] Delete confirmation auto-resets after 3 seconds (same pattern as account delete)
- [x] All actions keyboard accessible
- [x] E2E test for duplicating a transaction from detail sheet

## Technical Notes

- Template: `backend/transactions/templates/transactions/_transaction_detail_sheet.html`
- Duplicate: link to `/transactions/new?dup={{ tx.id }}` (pattern already exists in `_transaction_row.html:66`)
- Recurring badge: check `tx.recurring_rule_id` in template context
- Delete confirmation: reuse two-step pattern from `account_detail.html:282-322`

## Progress Notes

- 2026-03-31: Created — makes transaction detail more actionable
- 2026-04-22: Implemented recurring badge, duplicate action, and two-step delete confirmation. Added unit and E2E tests.
