---
id: "107"
title: "Notification model and migration"
type: feature
priority: high
status: wip
created: 2026-04-04
updated: 2026-04-04
---

## Description

Add a persistent `Notification` model to `push/models.py` to store notification state (read/unread) in the database. This is the foundation for the notification center feature — all subsequent tickets depend on this model.

Currently, notifications are stateless (recalculated on every poll). This ticket adds the DB layer that enables read/unread tracking, notification history, and the notification center UI.

## Acceptance Criteria

- [ ] `Notification` model added to `push/models.py` with fields: id (UUID PK), user (FK), title, body, url, tag, is_read, created_at, updated_at
- [ ] `UniqueConstraint(fields=["user", "tag"], name="notifications_user_tag_unique")` prevents duplicate notifications per user
- [ ] Composite index on `(user, is_read, -created_at)` for efficient queries
- [ ] Uses `UserScopedManager` for automatic user filtering
- [ ] Migration generated and applied cleanly (`makemigrations push` + `migrate`)
- [ ] Tests: model creation, unique constraint enforcement, UserScopedManager filtering, ordering by `-created_at`

## Technical Notes

Model follows existing conventions:
- UUID PK with `default=uuid.uuid4, db_default=GEN_UUID`
- FK to `auth_app.User` with `db_column="user_id"`
- `db_table = "notifications"`
- `auto_now_add` / `auto_now` timestamps with `db_default=Now()`

Files:
- `backend/push/models.py` (new)
- `backend/push/migrations/0001_notification.py` (auto-generated)
- `backend/push/tests/test_models.py` (new)

## Progress Notes

- 2026-04-04: Created — Notification center design approved, starting with data model
