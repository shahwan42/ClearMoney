---
id: "142"
title: "Generalized person currency balance storage"
type: feature
priority: high
status: done
created: 2026-04-22
updated: 2026-04-23
---

## Description

Replace `Person.net_balance_egp` and `Person.net_balance_usd` with generalized
per-person-per-currency storage so people balances can work for any active
currency without dual-field branching.

## Details

- Add a `PersonCurrencyBalance` model keyed by `(person, currency)`
- Backfill from legacy `net_balance_egp` and `net_balance_usd` fields
- Update loan and repayment write paths to mutate the balance row matching the
  transaction account currency
- Preserve legacy columns only as temporary compatibility during rollout
- Add admin and factory support for the new balance model

## Acceptance Criteria

- [x] People balances persist correctly for any active currency
- [x] Existing EGP and USD balances are fully backfilled
- [x] Loan and repayment flows write to generalized currency rows
- [x] Unique `(person, currency)` balance invariants are enforced
- [x] No people mutation path depends on `net_balance_egp` / `net_balance_usd`

## Critical Files

- `backend/people/models.py`
- `backend/people/services.py`
- `backend/people/admin.py`
- `backend/people/migrations/`
- `backend/tests/factories.py`

## Unit Tests

- Backfill migration from legacy balance fields
- Loan and repayment updates in a third currency
- Unique-constraint behavior on `(person, currency)`
- Sign handling when repayments cross through zero

## E2E Tests

- Lend and repay in a non-USD/EGP currency from the UI
- Existing users retain correct visible balances after migration

## Dependencies

- Depends on `#139`

## Progress Notes

- 2026-04-22: Created as the first domain-model generalization ticket
- 2026-04-23: Moved to `wip` and implemented `PersonCurrencyBalance` with a
  migration backfill from the legacy `net_balance_egp` / `net_balance_usd`
  columns while preserving those fields as compatibility mirrors
- 2026-04-23: Switched loan and repayment writes to the generalized balance
  rows, updated people service payloads and templates to render dynamic balance
  lists, and added admin/factory support plus migration, service, view, and E2E
  coverage for third-currency behavior
- 2026-04-23: Verified with `make test` (1544 passed), `make test-e2e` (271
  passed), `python backend/manage.py makemigrations --check --dry-run`,
  `python backend/manage.py check`, targeted `ruff check`, and targeted `mypy`
  on the touched modules
- 2026-04-23: Completed — people balances now persist per person and per
  registry-backed currency without dual-field branching in mutation paths
