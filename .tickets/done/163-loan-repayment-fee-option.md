---
id: "163"
title: "Loan repayment fee option"
type: feature
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Add optional fee field to loan repayment creation. Fee deducts from same account as repayment, does not affect person's balance debt settlement, creation only (no edit support).

## Acceptance Criteria

- [x] `record_repayment()` accepts optional `fee_amount` param
- [x] Fee creates linked expense transaction via `create_fee_for_transaction()`
- [x] Person balance unchanged by fee (only repayment amount settles debt)
- [x] Fee field in repayment form (between note and submit)
- [x] Service tests: fee tx created + linked, person balance unaffected
- [x] View tests: fee field parsed correctly (HTMX + JSON API)

## Progress Notes

- 2026-04-27: Started — implementing fee support for loan repayments
- 2026-04-27: Completed — service, views, template, 4 new tests (1571 passing)
