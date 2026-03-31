---
id: "073"
title: "Shared expense splitting"
type: feature
priority: low
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Tag transactions as shared with a person and auto-create loan records for the other person's share. Simplifies splitting bills and tracking settlements.

## Acceptance Criteria

- [ ] "Split with" option on transaction create/edit — select a Person
- [ ] Split ratio: 50/50 (default), custom amount, or custom percentage
- [ ] Auto-create `loan_out` transaction for the other person's share
- [ ] Settlement tracking: show outstanding split balances per person
- [ ] Quick settle: mark split as settled, create `loan_repayment` transaction
- [ ] Split history visible on Person detail page
- [ ] Service-layer tests for split creation, settlement, balance tracking
- [ ] E2E test for creating split → viewing on person page → settling

## Technical Notes

- Builds on existing `People` app and loan transaction types
- New field on Transaction: `split_person_id` (FK Person, nullable) or use `person_id`
- Split creates two linked transactions: original expense + loan_out to person
- Reuse existing `TransactionService.create()` with `type="loan_out"`
- Settlement reuses `type="loan_repayment"`

## Progress Notes

- 2026-03-31: Created — planned as Tier 3 feature recommendation
