---
id: "007"
title: "Phase 3 Cleanup — update import sites and remove shims"
type: chore
priority: medium
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

Phase 3 (model migration) is complete. All 18 models now live in owning apps, with re-export shims in `core/models.py` providing backward compatibility. This cleanup removes those shims by updating all 44 files (55 import statements) to import directly from owning apps, then re-enables import-linter contracts.

Pure refactor — zero behavioral changes, zero schema changes (3 state-only migrations created for architectural fix).

## Acceptance Criteria

- [x] All 44 files updated to import from owning apps (not `core.models`)
- [x] `core/models.py` emptied to docstring only
- [x] import-linter contracts re-enabled in `backend/pyproject.toml`
- [x] `grep -r "from core.models import" backend/ --include="*.py" | grep -v "models.py:"` returns empty
- [x] `make test` passes >= 1157
- [x] `make lint` shows "Contracts: 2 kept, 0 broken"

## Progress Notes

- 2026-03-28: Started — Updating all 44 import sites across infrastructure, services, views, and test files
- 2026-03-28: Completed — All 44 files updated, core.models emptied, contracts re-enabled. Extra work: moved AccountSnapshot to accounts.models and DailySnapshot to auth_app.models (3 state-only migrations) to resolve import-linter contract violations. Final: 1157 tests passing, Contracts: 2 kept, 0 broken, zero mypy errors.
