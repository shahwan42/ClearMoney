---
id: "105"
title: "Custom delete confirmation dialog"
type: improvement
priority: medium
status: done
created: 2026-03-31
updated: 2026-04-18
---

## Description

Swipe-to-delete on transactions uses the browser's native `confirm()` dialog (plain "OK/Cancel" with no styling). Replace with an app-native confirmation dialog that matches ClearMoney's visual design.

## Acceptance Criteria

- [x] Custom modal/bottom-sheet confirmation replaces browser `confirm()` on swipe-to-delete
- [x] Dialog shows: "Delete this transaction?" with transaction summary (amount, note, date)
- [x] Two buttons: "Cancel" (secondary) and "Delete" (red, destructive)
- [x] Dialog has `role="alertdialog"` with `aria-modal="true"` and `aria-labelledby`
- [x] Focus trapped inside dialog; Escape dismisses (same as other bottom sheets)
- [x] Focus returns to transaction row after cancel
- [x] Smooth open/close animation consistent with existing bottom sheets
- [x] Works in both light and dark modes
- [x] Also replace any other `hx-confirm` browser dialogs across the app (budget delete, recurring delete, account delete, etc.)
- [x] E2E test for swipe → custom dialog appears → cancel → row restored
- [x] E2E test for swipe → custom dialog → confirm delete → row removed

## Technical Notes

- Current: `gestures.js` calls `confirm("Delete this transaction?")` (browser native)
- Also: `hx-confirm` attribute used on various delete buttons across templates
- Create reusable `static/js/confirm-dialog.js` module exposing `showConfirmDialog(options)` → returns Promise<boolean>
- Options: `{ title, message, confirmText, confirmClass, cancelText }`
- Template: `backend/templates/components/_confirm_dialog.html` (shared partial)
- HTMX integration: override `htmx:confirm` event to use custom dialog instead of native confirm
- Reuse existing bottom sheet animation and focus-trap patterns from `bottom-sheet.js`

## Progress Notes

- 2026-03-31: Created — replaces all browser-native confirm() dialogs with branded UX
- 2026-04-18: Implemented
  - Created `static/js/confirm-dialog.js` — reusable dialog module with Promise-based API
  - Created `static/js/htmx-confirm-dialog.js` — HTMX extension to intercept `hx-confirm` attributes
  - Created `backend/templates/components/_confirm_dialog.html` — accessible bottom-sheet dialog
  - Updated `gestures.js` to use custom dialog with transaction summary
  - Updated templates: transaction row, transaction detail sheet, recurring rules, investments
  - Added 4 E2E tests covering swipe → dialog → cancel/confirm flows
  - All acceptance criteria met

## Files Changed

- `static/js/confirm-dialog.js` (new)
- `static/js/htmx-confirm-dialog.js` (new)
- `backend/templates/components/_confirm_dialog.html` (new)
- `backend/templates/base.html` (updated)
- `static/js/gestures.js` (updated)
- `backend/transactions/templates/transactions/_transaction_row.html` (updated)
- `backend/transactions/templates/transactions/_transaction_detail_sheet.html` (updated)
- `backend/recurring/templates/recurring/_rule_list.html` (updated)
- `backend/investments/templates/investments/investments.html` (updated)
- `e2e/tests/test_transactions.py` (updated)
