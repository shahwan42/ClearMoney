---
id: "012"
title: "Add optional fee to expense/income transactions"
type: feature
priority: medium
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

Add an optional fee field to the transaction creation form (inside "More options"). When a fee is provided, create a separate linked expense transaction auto-categorized as "Fees & Charges" — same pattern already used for transfer fees.

## Acceptance Criteria

- [x] Fee input appears in "More options" section of transaction_new.html
- [x] Fee creates a separate expense transaction linked to the parent
- [x] Fee transaction is auto-categorized as "Fees & Charges"
- [x] Account balance is debited by amount + fee (for expenses)
- [x] No fee transaction created when fee is 0 or empty
- [x] Service, view, and E2E tests cover fee creation

## Progress Notes

- 2026-03-28: Started — Reading existing transfer fee pattern, planning implementation
- 2026-03-28: Completed — All acceptance criteria verified: fee field in template, service + view + E2E tests passing (1184 tests, lint clean)
