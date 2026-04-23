---
id: "150"
title: "Generalized snapshot model and historical backfill"
type: feature
priority: high
status: done
created: 2026-04-22
updated: 2026-04-23
---

## Description

Redesign historical aggregate storage so net-worth and related history can be
queried dynamically by currency rather than through EGP-canonical snapshot
fields.

## Details

- Replace or augment `DailySnapshot` with a per-date per-currency historical
  structure
- Backfill existing historical data from account snapshots and existing balances
- Keep the backfill idempotent and safe for existing users
- Review related daily income/spending metrics for currency-specific handling
- Avoid JSON-only storage if it would make dynamic historical queries or testing
  fragile

## Acceptance Criteria

- [x] Historical per-currency totals can be queried for any active currency
- [x] Existing users retain historical continuity after migration
- [x] Snapshot generation no longer depends on EGP-canonical net-worth fields
- [x] Backfill can be rerun safely without duplicating or corrupting history

## Critical Files

- `backend/auth_app/models.py`
- `backend/jobs/services/snapshot.py`
- `backend/accounts/models.py`
- `backend/dashboard/services/sparklines.py`
- `backend/tests/factories.py`
- `backend/auth_app/admin.py`

## Unit Tests

- Historical backfill from account snapshots
- Per-currency snapshot query correctness
- Idempotent rerun behavior
- Third-currency historical series generation

## E2E Tests

- Existing seeded history survives migration
- Snapshot jobs continue to run successfully after the redesign

## Dependencies

- Depends on `#145`

## Progress Notes

- 2026-04-22: Created for historical multi-currency support
- 2026-04-23: Started — planned generalized per-currency historical snapshots, snapshot job refactor, migration backfill, and dashboard query updates
- 2026-04-23: Completed — added canonical `HistoricalSnapshot` storage, migration backfill from account/daily snapshot data, dashboard history reads from canonical rows, idempotent snapshot/backfill coverage, and repo-wide verification (`make test`, `make lint`, full E2E suite)
