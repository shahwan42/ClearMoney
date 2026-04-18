---
id: "111"
title: "Mark as read + mark all as read"
type: feature
priority: high
status: done
created: 2026-04-04
updated: 2026-04-18
---

## Description

Add actions to mark individual notifications as read (with redirect to action URL) and mark all notifications as read. These complete the core notification center interaction flow.

**Depends on**: #110

## Acceptance Criteria

- [x] `POST /notifications/<uuid>/read` marks notification `is_read=True` and redirects to `notification.url`
- [x] If `notification.url` is empty, redirects to `/notifications`
- [x] Returns 404 if notification belongs to a different user
- [x] Already-read notifications: still redirects (idempotent), doesn't error
- [x] `POST /notifications/mark-all-read` bulk updates all unread → read for current user
- [x] Mark-all-read: HTMX response re-renders notification list, or redirects for standard request
- [x] "Mark All as Read" button visible on notifications page only when unread notifications exist
- [x] Each notification card is clickable — wraps in a form that POSTs to mark-read endpoint
- [x] Works with both HTMX and standard form submission (progressive enhancement)
- [x] Tests: mark single read + verify redirect, mark all read, 404 for other user's notification, already-read stays read, empty mark-all is no-op

## Technical Notes

Files:
- `backend/push/views.py` (modify — add mark_read and mark_all_read views)
- `backend/push/urls.py` (modify — add action URLs)
- `backend/push/templates/push/notifications.html` (modify — add forms and mark-all button)
- `backend/push/tests/test_views.py` (modify — add action tests)

## Progress Notes

- 2026-04-04: Created — Depends on #110 (notifications list page)
- 2026-04-18: Completed — mark_read and mark_all_read views, HTMX-aware mark-all, 7 tests pass.
