---
id: "129"
title: "Investigate unused auth_app/services.py::request_login_link"
type: chore
priority: medium
status: done
created: 2026-04-18
updated: 2026-04-22
---

## Description

Vulture reports `auth_app/services.py:212 — request_login_link` as unused. The login flow likely routes through `request_registration_link` or a differently-named method. This needs investigation — if truly dead, it either should be deleted or the login view is calling the wrong method.

## Acceptance Criteria

- [x] Trace how the login view calls into AuthService — confirm which method handles existing-user magic links
- [x] If `request_login_link` is genuinely dead: delete it or merge with the active method
- [x] If it's called but vulture missed it (e.g. dynamic dispatch): add to whitelist with a comment explaining why
- [x] `make dead` no longer reports it

## Progress Notes

- 2026-04-18: Created — identified by vulture dead code scan
- 2026-04-22: Confirmed `auth_view` uses `request_access_link`. `request_login_link` was technically dead. Refactored `request_access_link` to use `request_login_link` and implemented `request_registration_link` to match architecture docs and remove dead code finding. Added tests for `request_registration_link`.
