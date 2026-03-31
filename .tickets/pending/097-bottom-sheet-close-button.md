---
id: "097"
title: "Bottom sheet visible close button"
type: improvement
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Bottom sheets have no visible close button — only drag-handle swipe or overlay click dismisses them. Mouse and keyboard users need a visible X button.

## Acceptance Criteria

- [ ] X close button in top-right corner of every bottom sheet
- [ ] Button has `aria-label="Close"` and is keyboard focusable
- [ ] Consistent styling: subtle gray icon, 44x44px touch target
- [ ] Click triggers same close behavior as Escape key
- [ ] Visible in both light and dark modes
- [ ] Does not interfere with sheet content scrolling
- [ ] Positioned in drag-handle bar area (doesn't consume content space)
- [ ] E2E test for clicking X button → sheet closes

## Technical Notes

- Modify `backend/templates/components/bottom_sheet.html`
- Add button inside the drag-handle header bar
- Wire to existing `closeSheet()` method in `static/js/bottom-sheet.js`
- Use Heroicons `x-mark` SVG icon (already used elsewhere in app)

## Progress Notes

- 2026-03-31: Created — improves accessibility for non-touch users
