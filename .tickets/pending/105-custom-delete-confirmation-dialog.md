---
id: "105"
title: "Custom delete confirmation dialog"
type: improvement
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Swipe-to-delete on transactions uses the browser's native `confirm()` dialog (plain "OK/Cancel" with no styling). Replace with an app-native confirmation dialog that matches ClearMoney's visual design.

## Acceptance Criteria

- [ ] Custom modal/bottom-sheet confirmation replaces browser `confirm()` on swipe-to-delete
- [ ] Dialog shows: "Delete this transaction?" with transaction summary (amount, note, date)
- [ ] Two buttons: "Cancel" (secondary) and "Delete" (red, destructive)
- [ ] Dialog has `role="alertdialog"` with `aria-modal="true"` and `aria-labelledby`
- [ ] Focus trapped inside dialog; Escape dismisses (same as other bottom sheets)
- [ ] Focus returns to transaction row after cancel
- [ ] Smooth open/close animation consistent with existing bottom sheets
- [ ] Works in both light and dark modes
- [ ] Also replace any other `hx-confirm` browser dialogs across the app (budget delete, recurring delete, account delete, etc.)
- [ ] E2E test for swipe → custom dialog appears → cancel → row restored
- [ ] E2E test for swipe → custom dialog → confirm delete → row removed

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
