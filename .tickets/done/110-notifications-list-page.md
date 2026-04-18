---
id: "110"
title: "Notifications list page"
type: feature
priority: high
status: done
created: 2026-04-04
updated: 2026-04-18
---

## Description

Add a dedicated notifications page at `GET /notifications` showing all user notifications grouped by unread/read status. Each notification displays title, body, and relative timestamp.

**Depends on**: #107

## Acceptance Criteria

- [ ] `GET /notifications` view renders `push/notifications.html` template
- [ ] Template extends `base.html` with page title "Notifications"
- [ ] Unread notifications shown first with visual distinction (bold title, colored left border)
- [ ] Read notifications shown in "Earlier" section with muted styling
- [ ] Each notification card shows: title, body text, relative timestamp (e.g., "2 hours ago")
- [ ] Empty state: bell icon + "No notifications yet" text when no notifications exist
- [ ] Data isolation: users can only see their own notifications (uses `UserScopedManager`)
- [ ] Accessible: semantic HTML, proper heading hierarchy, `aria-label` on interactive elements
- [ ] Dark mode compatible (Tailwind dark: classes)
- [ ] Tests: view returns 200, shows unread first, data isolation (404/empty for other user), empty state renders

## Technical Notes

Files:
- `backend/push/views.py` (modify — add notifications_page view)
- `backend/push/urls.py` (modify — add /notifications URL)
- `backend/push/templates/push/notifications.html` (new)
- `backend/push/tests/test_views.py` (modify — add page tests)

## Progress Notes

- 2026-04-04: Created — Depends on #107 (notification model)
- 2026-04-18: Completed — All acceptance criteria met; feature shipped in commit 7a68a12
