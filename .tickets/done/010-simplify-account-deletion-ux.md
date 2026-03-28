---
id: "010"
title: "Simplify account & institution deletion UX"
type: improvement
priority: medium
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

Replace the type-to-confirm deletion pattern with a simpler two-step button confirmation for both accounts and institutions. No typing needed — first tap arms the button ("Tap again to confirm"), second tap deletes. Auto-resets after 3 seconds.

## Acceptance Criteria

- [x] Account delete bottom sheet uses two-step button instead of text input
- [x] Institution delete confirmation uses two-step button instead of text input
- [x] Button shows "Tap again to confirm" with visual feedback after first click
- [x] Auto-resets to initial state after 3 seconds if not confirmed
- [x] Screen readers announce the state change (aria-live)
- [x] All existing unit and E2E tests updated and passing
- [x] No backend changes needed

## Progress Notes

- 2026-03-28: Started — replacing type-to-confirm with two-step button pattern
- 2026-03-28: Completed — Two-step confirm button implemented for both accounts and institutions (commit b4af94a).
