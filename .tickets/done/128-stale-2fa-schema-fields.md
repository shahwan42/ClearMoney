---
id: "128"
title: "Stale 2FA schema: pin_hash, session_key, failed_attempts, locked_until on Session model"
type: chore
priority: medium
status: done
created: 2026-04-18
updated: 2026-04-22
---

## Description

Vulture found four columns on `auth_app/models.py` (the `Session` model) that are never accessed in Python code:

- `:73` — `pin_hash`
- `:74` — `session_key`
- `:75` — `failed_attempts`
- `:76` — `locked_until`

These look like a leftover 2FA / PIN lock feature that was planned or partially implemented but never used.

## Acceptance Criteria

- [x] Confirm none of these fields are read/written anywhere in services, views, or templates
- [x] If dead: create migration to drop the columns (multi-step: check prod data first)
- [x] Remove fields from model
- [x] `make dead` no longer reports them

## Progress Notes

- 2026-04-18: Created — identified by vulture dead code scan
- 2026-04-22: Removed stale fields from `UserConfig` model, admin, and factories. Applied migration. Verified with `make dead` and `make test` (unrelated dashboard failure noted).
