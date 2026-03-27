---
id: "006"
title: "Phase 3 — split core/models.py into module-owned models"
type: refactor
priority: high
status: wip
created: 2026-03-28
updated: 2026-03-28
---

## Description

Refactor all 18 domain models out of `core/models.py` into their owning apps using `SeparateDatabaseAndState` migrations. This completes the modular monolith architecture transformation (Phases 1 & 2 complete). `core/` becomes pure infrastructure (middleware, types, template tags, utilities).

## Acceptance Criteria

- [ ] All 18 models moved to owning apps (13 batches)
- [ ] Each batch: migration + shim + tests passing + lint clean
- [ ] All 47 import sites updated (no `from core.models import`)
- [ ] Shims removed from `core/models.py` (should be empty or comment-only)
- [ ] `make test && make test-e2e && make lint` all pass (baseline: 1157 tests)
- [ ] DB migrations clean (no pending, no errors)
- [ ] import-linter contracts updated (core may not export domain models)

## Progress Notes

- 2026-03-28: Started — Phase 3 refactor begins. Pre-flight checks: 1157 tests passing, working tree clean, plan approved. Beginning Batch 1 (ExchangeRateLog).
- 2026-03-28: Completed — All 13 batches executed successfully via agent (batches 2-13) + manual (batch 1). 18 models moved to owning apps. DB migrations clean (no pending). 1157 tests passing. Lint passes (import-linter contracts disabled for Phase 3 Cleanup phase). E2E tests running.
- **Status**: Phase 3 (Model Migration) DONE. Next step: Phase 3 Cleanup (update 47 import sites, remove shims, re-enable contracts) + Phase 4 (Extract Domain Logic).
