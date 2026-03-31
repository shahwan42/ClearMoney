---
id: "103"
title: "Swipe-to-delete safety improvements"
type: improvement
priority: low
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Current swipe-to-delete threshold is 60px which can trigger accidentally. Increase safety by requiring an explicit tap on the revealed delete button instead of auto-triggering on swipe distance.

## Acceptance Criteria

- [ ] Swipe left reveals red delete button (no auto-trigger on distance)
- [ ] User must explicitly tap the revealed "Delete" button to trigger deletion
- [ ] Swipe right or tap elsewhere dismisses the revealed button (resets row)
- [ ] Delete button has clear "Delete" text label (not just icon)
- [ ] Confirmation dialog still appears after tapping delete button
- [ ] Smooth animation for reveal and reset
- [ ] Keyboard alternative: delete via kebab menu (already exists)
- [ ] E2E test for swipe → reveal button → tap → confirm → deleted

## Technical Notes

- File: `static/js/gestures.js` (swipe-to-delete section)
- Current: 60px swipe auto-triggers delete confirmation dialog
- Change: swipe reveals button, button click triggers confirmation
- Add `data-swipe-revealed` state to track revealed rows
- Only one row can be revealed at a time (revealing another resets the first)

## Progress Notes

- 2026-03-31: Created — prevents accidental transaction deletion
