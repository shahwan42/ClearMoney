---
id: "112"
title: "E2E tests for notification center"
type: test
priority: medium
status: wip
created: 2026-04-04
updated: 2026-04-04
---

## Description

Add Playwright end-to-end tests covering the full notification center user journey: bell icon visibility, unread badge, clicking notifications, mark-all-as-read, and empty state.

**Depends on**: #108, #109, #110, #111

## Acceptance Criteria

- [ ] E2E test: Bell icon visible in header on all pages
- [ ] E2E test: Badge shows correct unread count after notifications are generated
- [ ] E2E test: Click a notification → marked as read + redirected to action URL
- [ ] E2E test: Badge count decreases after marking notification as read
- [ ] E2E test: "Mark All as Read" clears all unread, badge disappears
- [ ] E2E test: Empty state shown when no notifications exist
- [ ] E2E test: Data isolation — user A cannot see user B's notifications
- [ ] All tests pass in `make test-e2e`
- [ ] Tests follow existing patterns in `e2e/tests/` (fixtures, auth helpers, DB setup)

## Technical Notes

Files:
- `e2e/tests/test_notifications.py` (new)

May need to seed notifications in DB directly (via SQL or Django management command) as part of test setup, since notification generation depends on having accounts/budgets/recurring rules.

## Progress Notes

- 2026-04-04: Created — Depends on #108, #109, #110, #111
