---
id: "164"
title: "Fee presets model + seed"
type: feature
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Foundation for easier fee selection (InstaPay/ATM/Custom): introduce `FeePreset` model with per-currency, per-user fee rules. Seed defaults (InstaPay percent 0.1% min 0.5 max 20; ATM flat 5) for new users on registration and existing users via data migration. Adds nullable `fee_preset_id` FK to Transaction.

Related follow-ups (separate tickets):
- 165: Settings CRUD page `/settings/fee-presets`
- 166: Form pill selector + reports FK integration

## Acceptance Criteria

- [x] `FeePreset` model in new `fee_presets` app — chose dedicated app over `core/models.py` since core was already drained in Phase 3 migration
- [x] `db_table = "fee_presets"`, unique_together (user_id, name, currency)
- [x] `Transaction.fee_preset_id` nullable FK added (additive, backward-compatible)
- [x] Migrations generated and applied (`fee_presets/0001_initial`, `fee_presets/0002_seed_existing_users`, `transactions/0009_transaction_fee_preset`)
- [x] New user registration seeds EGP InstaPay + ATM presets (wired in `auth_app/services.py` after category seeding)
- [x] Data migration seeds existing users (idempotent via `get_or_create`)
- [x] Service helper `compute_fee(preset, amount) -> Decimal` returns clamped percent or flat amount
- [x] Tests: 27 new tests in `fee_presets/tests/` covering model, compute, service, isolation, seed idempotency; auth registration test extended to assert preset seeding
- [x] Coverage maintained: 1595 → 1622 passed (+27)

## Progress Notes

- 2026-04-27: Started — design grilled out, approach: model + nullable FK + seed via signal/registration + data migration for existing users
- 2026-04-27: Completed — model + service + 2 migrations + 27 tests + auth seeding wired. Lint clean, mypy clean, Django check clean. Pre-existing recurring test failure unrelated.
