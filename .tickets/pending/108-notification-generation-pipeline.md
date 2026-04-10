---
id: "108"
title: "Notification generation pipeline"
type: feature
priority: high
status: wip
created: 2026-04-04
updated: 2026-04-04
---

## Description

Add a `generate_and_persist()` method to `NotificationService` that persists notification payloads to the database using `update_or_create` with tag-based deduplication. Add management commands for generation and cleanup, and integrate into the background job pipeline.

**Depends on**: #107

## Acceptance Criteria

- [ ] `generate_and_persist()` method on `NotificationService` that:
  - Calls existing `get_pending_notifications()` for current payloads
  - Upserts each payload via `Notification.objects.update_or_create(user_id, tag, defaults={...})`
  - Sets `is_read=False` on upsert (re-alerts if condition recurs after user read it)
  - Auto-resolves: deletes UNREAD notifications whose tags are NOT in current payload set
  - Preserves read notifications for resolved conditions (until 30-day cleanup)
  - Returns stats (created, updated, resolved counts)
- [ ] `generate_notifications` management command: iterates all users, calls `generate_and_persist()` per user, try/except per user
- [ ] `cleanup_notifications` management command: deletes notifications older than 30 days
- [ ] `generate_notifications` added to `run_startup_jobs` (after `process_recurring`, before `refresh_views`)
- [ ] Both commands added to `docker-compose.prod.yml` cron loop
- [ ] Tests: upsert creates new, updates existing, resolves stale, preserves read history, cleanup deletes old, command runs without error

## Technical Notes

Files:
- `backend/push/services.py` (modify — add method)
- `backend/push/management/commands/generate_notifications.py` (new)
- `backend/push/management/commands/cleanup_notifications.py` (new)
- `backend/jobs/management/commands/run_startup_jobs.py` (modify — add to jobs list)
- `docker-compose.prod.yml` (modify — add to cron loop)
- `backend/push/tests/test_services.py` (modify — add persistence tests)
- `backend/push/tests/test_commands.py` (modify — add command tests)

## Progress Notes

- 2026-04-04: Created — Depends on #107 (notification model)
