---
id: "012"
title: "Add optional fee to expense/income transactions"
type: feature
priority: medium
status: wip
created: 2026-03-28
updated: 2026-03-28
---

## Description

Add an optional fee field to the transaction creation form (inside "More options"). When a fee is provided, create a separate linked expense transaction auto-categorized as "Fees & Charges" — same pattern already used for transfer fees.

## Acceptance Criteria

- [ ] Fee input appears in "More options" section of transaction_new.html
- [ ] Fee creates a separate expense transaction linked to the parent
- [ ] Fee transaction is auto-categorized as "Fees & Charges"
- [ ] Account balance is debited by amount + fee (for expenses)
- [ ] No fee transaction created when fee is 0 or empty
- [ ] Service, view, and E2E tests cover fee creation

## Progress Notes

- 2026-03-28: Started — Reading existing transfer fee pattern, planning implementation
