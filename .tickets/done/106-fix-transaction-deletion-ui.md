---
id: "106"
title: "Fix transaction deletion UI for related transactions"
type: bug
priority: medium
status: done
created: 2026-03-31
updated: 2026-03-31
---

## Description

When deleting a transfer/exchange transaction from the history page, the backend correctly deletes both linked transactions (and fees) atomically, but the UI only removes the row the user clicked. The linked transaction row stays visible until page refresh, giving false information about balances.

## Acceptance Criteria

- [x] `delete()` returns IDs of related transactions also deleted
- [x] View returns HTMX OOB delete elements for related rows
- [x] Swipe-to-delete also removes related rows via response header
- [x] Existing tests updated, new tests added
- [x] All tests pass, zero lint errors

## Progress Notes

- 2026-03-31: Started — Investigating transaction deletion flow across service, view, and UI layers
- 2026-03-31: Completed — Service returns related IDs, view returns OOB swaps + header, gestures.js handles header. 1226 tests pass, zero lint errors.
