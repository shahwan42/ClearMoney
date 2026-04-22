---
id: "153"
title: "Cleanup, compatibility removal, docs, and guardrails"
type: chore
priority: medium
status: pending
created: 2026-04-22
updated: 2026-04-22
---

## Description

Remove transitional dual-currency compatibility paths, update docs and seed
data, and add product guardrails once the generalized multi-currency rollout is
complete.

## Details

- Remove legacy dual-currency fields and compatibility code after all runtime
  consumers are migrated
- Update docs, seed data, factories, admin configuration, and QA scenarios for
  third-currency coverage
- Prevent users from deactivating currencies still referenced by live data
- Ensure any remaining USD/EGP exchange-rate behavior is explicitly isolated as
  legacy FX functionality rather than part of generalized summary calculations

## Acceptance Criteria

- [ ] No production path depends on dual-currency-only domain structures
- [ ] Currency deactivation guardrails prevent inconsistent user state
- [ ] Docs and seed/factory data reflect generalized multi-currency behavior
- [ ] Test coverage includes non-USD/EGP cases in all major domains

## Critical Files

- `backend/tests/factories.py`
- `backend/jobs/management/commands/qa_seed.py`
- `backend/auth_app/models.py`
- `backend/settings_app/views.py`
- `docs/`

## Unit Tests

- Currency deactivation guardrails
- Legacy field-removal safety
- Factory and seed support for third-currency scenarios

## E2E Tests

- Seeded multi-currency user behaves correctly end to end
- Settings prevents invalid currency deactivation

## Dependencies

- Depends on `#142`
- Depends on `#151`
- Depends on `#152`

## Progress Notes

- 2026-04-22: Created as the final cleanup and hardening ticket

