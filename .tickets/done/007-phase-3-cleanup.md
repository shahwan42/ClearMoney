---
id: "007"
title: "Phase 3 Cleanup — update import sites, remove shims, re-enable contracts"
type: refactor
priority: high
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

Remove all backward-compatibility re-export shims from `core/models.py` by updating all 44 Python files to import models directly from owning apps. Re-enable import-linter contracts.

Discovered and fixed architectural issue: `AccountSnapshot` and `DailySnapshot` were incorrectly in `jobs` (aggregator). Moved to `accounts` and `auth_app` (owning services).

## Acceptance Criteria

- [x] All 56 import statements updated to direct per-app imports
- [x] Zero remaining `from core.models import` in backend code
- [x] `core/models.py` emptied to docstring only
- [x] All inline method imports moved to top-level
- [x] import-linter contracts re-enabled (2 kept, 0 broken)
- [x] Tests pass (1157 passing)
- [x] Migrations clean (no pending)
- [x] Lint passes (zero errors)

## Architectural Fix Applied

**Issue discovered:** `AccountSnapshot` and `DailySnapshot` were in `jobs/models.py`, which is an aggregator. This violated the modular monolith boundary when leaf modules imported them.

**Solution:**
- Moved `AccountSnapshot` to `accounts/models.py` (owning service)
- Moved `DailySnapshot` to `auth_app/models.py` (owning service)
- Created 3 state-only migrations (no DB changes) to register models in new locations
- Updated all 6 import sites (accounts/services.py, jobs/services/snapshot.py, etc.)

**Result:** All imports now respect boundaries. Import-linter contracts pass cleanly.

## Progress Notes

- 2026-03-28: Started Phase 3 Cleanup — 44 files, 56 import statements
- 2026-03-28: Completed — All imports updated, shims removed, contracts re-enabled
- 2026-03-28: Architectural fix applied — moved DailySnapshot & AccountSnapshot to owning apps
- 2026-03-28: Verified — 0 remaining core.models imports, 1157 tests passing, contracts: 2 kept 0 broken

## Commits

- Phase 3 Cleanup main commit (import updates + core/models.py emptied + contracts re-enabled)
- Architectural fix: Move DailySnapshot to auth_app, AccountSnapshot to accounts (with migrations)
