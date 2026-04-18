---
id: "109"
title: "Bell icon with unread badge in header"
type: feature
priority: high
status: done
created: 2026-04-04
updated: 2026-04-18
---

## Description

Add a notification bell icon to the header bar with a red unread count badge. The badge updates via HTMX polling every 60 seconds and is also server-rendered on initial page load via a context processor.

**Depends on**: #107

## Acceptance Criteria

- [ ] Context processor `push.context_processors.unread_notification_count` returns `{"unread_notification_count": int}`
- [ ] Context processor registered in `settings.py` TEMPLATES config
- [ ] Context processor guards unauthenticated requests (returns empty dict)
- [ ] Bell icon (Heroicons outline bell SVG, h-5 w-5) added to header between theme toggle and reports icon
- [ ] Bell icon follows same styling as existing header icons (text-slate-300, hover:text-white, 44x44px touch target)
- [ ] Bell links to `/notifications`
- [ ] Red badge shown when unread > 0: absolute positioned, bg-red-500, text-white, rounded-full
- [ ] Badge hidden when unread = 0
- [ ] Badge has `hx-get="/notifications/badge"` with `hx-trigger="load, every 60s"` for live updates
- [ ] `GET /notifications/badge` view returns HTML fragment (badge partial)
- [ ] Tests: context processor count, badge view HTML fragment, zero count returns empty, auth required
- [ ] Accessible: `aria-label="Notifications"` on bell link, badge has `aria-hidden="true"` (count is decorative)

## Technical Notes

Files:
- `backend/push/context_processors.py` (new)
- `backend/push/templates/push/_badge.html` (new)
- `backend/push/views.py` (modify — add badge view)
- `backend/push/urls.py` (modify — add badge URL)
- `backend/templates/components/header.html` (modify — insert bell icon)
- `backend/clearmoney/settings.py` (modify — add context processor)

## Progress Notes

- 2026-04-04: Created — Depends on #107 (notification model)
- 2026-04-18: Completed — All acceptance criteria met; feature shipped in commit 7a68a12
