---
id: "021"
title: "Net worth debt calculation"
type: feature
priority: medium
status: done
created: 2026-03-29
updated: 2026-03-29
---

## Description

The Debt sub-card in the Net Worth section on the dashboard always shows 0 because `debt_total` is never computed. Implement the calculation to include:

1. All accounts with negative balances (credit cards, overdrafts, etc.)
2. Total borrowed money from people (Person records with negative `net_balance`)

Also update the debt breakdown drilldown to show people rows alongside negative-balance accounts.

## Acceptance Criteria

- [x] `debt_total` computed as sum of abs(negative account balances) + abs(people_i_owe)
- [x] Debt breakdown view includes people with negative balance
- [x] Unit tests cover: account debt only, people debt only, combined, zero debt
- [x] All existing tests still pass

## Progress Notes

- 2026-03-29: Started — Implementing debt_total calculation with TDD approach
- 2026-03-29: Completed — debt_total computed from negative account balances + people I owe, 6 tests added, 1211 total pass
