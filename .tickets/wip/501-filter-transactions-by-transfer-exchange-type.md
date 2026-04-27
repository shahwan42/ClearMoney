---
id: "501"
title: "Filter transactions by transfer and exchange type"
type: feature
priority: medium
status: wip
created: 2026-04-27
updated: 2026-04-27
---

## Description

Add "Transfer" and "Exchange" options to the type filter dropdown on the transaction history page. Backend already supports these filter values — only UI change needed.

## Acceptance Criteria

- [ ] "Transfer" option appears in type filter dropdown
- [ ] "Exchange" option appears in type filter dropdown
- [ ] Filtering by "Transfer" shows both legs of transfer transactions
- [ ] Filtering by "Exchange" shows both legs of exchange transactions
- [ ] Transfer fee transactions (type=expense) not shown under transfer filter

## Progress Notes

- 2026-04-27: Started — Added Transfer and Exchange options to dropdown in transactions.html
