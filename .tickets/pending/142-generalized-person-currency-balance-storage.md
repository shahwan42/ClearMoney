---
id: "142"
title: "Generalized person currency balance storage"
type: feature
priority: high
status: pending
created: 2026-04-22
updated: 2026-04-22
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

- [ ] People balances persist correctly for any active currency
- [ ] Existing EGP and USD balances are fully backfilled
- [ ] Loan and repayment flows write to generalized currency rows
- [ ] Unique `(person, currency)` balance invariants are enforced
- [ ] No people mutation path depends on `net_balance_egp` / `net_balance_usd`

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

