---
id: "097"
title: "Bottom sheet visible close button"
type: improvement
priority: medium
status: done
created: 2026-03-31
updated: 2026-03-31
---

## Description

Bottom sheets have no visible close button — only drag-handle swipe or overlay click dismisses them. Mouse and keyboard users need a visible X button.

## Acceptance Criteria

- [x] X close button in top-right corner of every bottom sheet
- [x] Button has `aria-label="Close"` and is keyboard focusable
- [x] Consistent styling: subtle gray icon, 44x44px touch target
- [x] Click triggers same close behavior as Escape key
- [x] Visible in both light and dark modes
- [x] Does not interfere with sheet content scrolling
- [x] Positioned in drag-handle bar area (doesn't consume content space)
- [x] E2E test for clicking X button → sheet closes

## Technical Notes

- Modify `backend/templates/components/bottom_sheet.html`
- Add button inside the drag-handle header bar
- Wire to existing `closeSheet()` method in `static/js/bottom-sheet.js`
- Use Heroicons `x-mark` SVG icon (already used elsewhere in app)

## Progress Notes

- 2026-03-31: Created — improves accessibility for non-touch users
- 2026-04-18: Implemented — added X close button to all bottom sheets (bottom_sheet.html template + bottom-nav.html inline sheets)
  - Button positioned in drag-handle bar (absolute top-right)
  - 44x44px touch target (p-3 padding + w-5 h-5 icon)
  - aria-label="Close" for screen readers
  - Keyboard focusable with visible focus ring
  - Same close behavior as Escape key and overlay click
  - Visible in light and dark modes (text-gray-500/dark:text-slate-400)
  - E2E tests: 7/7 passing
