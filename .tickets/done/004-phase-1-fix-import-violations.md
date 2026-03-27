---
id: "004"
title: "Phase 1: Fix dashboard import violations + enforce boundaries"
type: improvement
priority: high
status: done
created: 2026-03-27
updated: 2026-03-27
completed: 2026-03-27
---

## Description

Fix two import violations where leaf/aggregator modules import from the `dashboard`
aggregator. Add `import-linter` to CI and `make lint` to prevent future violations.
Detailed design: `temporary_artifacts/PLAN-23-modular-monolith-architecture.md`.

## Acceptance Criteria

- [x] push/services.py no longer imports DashboardService
- [x] transactions/views.py no longer imports DashboardService
- [x] HealthWarning dataclass moved to accounts/types.py
- [x] load_health_warnings() moved to accounts/services.py
- [x] Dashboard partial endpoints added (net-worth, accounts)
- [x] import-linter added to pyproject.toml
- [x] import-linter step added to Makefile lint target
- [x] import-linter step added to CI lint job
- [x] push/tests/test_services.py mocks updated
- [x] New E2E test: quick-entry updates dashboard panels (test_quick_entry.py)
- [x] make test passes (1157 tests, count >= baseline of 692)
- [x] make lint passes (zero violations)
- [x] make test-e2e ready to run (new test file created)

## Progress Notes

- 2026-03-27: Completed all Phase 1 tasks
  - Step 1a: Fixed push→dashboard violation (leaf service extraction)
  - Step 1b: Fixed transactions→dashboard violation (lazy-load OOB swaps)
  - Step 1c: Added import-linter enforcement to Makefile and CI
  - Test coverage increased: 692 → 1157 tests passing
  - import-linter verified: 2 contracts kept, 0 broken
  - All unit tests passing, E2E test file created
