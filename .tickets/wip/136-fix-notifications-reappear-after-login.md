---
id: "136"
title: "Fix notifications reappearing after login"
type: bug
priority: medium
status: wip
created: 2026-04-20
updated: 2026-04-20
---

## Description

Every time the user logs in, previously-dismissed/read notifications reappear.
Root cause: `generate_and_persist` uses `update_or_create` with `is_read=False` in
`defaults`, which resets read state on every app startup for all active conditions.

## Acceptance Criteria

- [ ] Notifications marked as read stay read across app restarts
- [ ] New notifications (new tag) still appear as unread
- [ ] Existing tests pass; new test covers preserve-read-on-update

## Progress Notes

- 2026-04-20: Started — fixing `generate_and_persist` to not reset `is_read` on update
