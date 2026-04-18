---
id: "112"
title: "E2E tests for notification center"
type: test
priority: medium
status: done
created: 2026-04-04
updated: 2026-04-18
---

## Description

Add Playwright end-to-end tests covering the full notification center user journey: bell icon visibility, unread badge, clicking notifications, mark-all-as-read, and empty state.

**Depends on**: #108, #109, #110, #111

## Acceptance Criteria

- [x] E2E test: Bell icon visible in header on all pages
- [x] E2E test: Badge shows correct unread count after notifications are generated
- [x] E2E test: Click a notification → marked as read + redirected to action URL
- [x] E2E test: Badge count decreases after marking notification as read
- [x] E2E test: "Mark All as Read" clears all unread, badge disappears
- [x] E2E test: Empty state shown when no notifications exist
- [x] E2E test: Data isolation — user A cannot see user B's notifications
- [x] All tests pass in `make test-e2e`
- [x] Tests follow existing patterns in `e2e/tests/` (fixtures, auth helpers, DB setup)

## Technical Notes

Files:
- `e2e/tests/test_notifications.py` (new)
- `e2e/conftest.py` (modify — add notifications to TRUNCATE list)

Notifications seeded directly in DB via psycopg (no Django management command needed).

## Progress Notes

- 2026-04-04: Created — Depends on #108, #109, #110, #111
- 2026-04-18: Completed — 14 E2E tests covering bell icon, badge, mark-read, mark-all-read, empty state, data isolation. All pass.
