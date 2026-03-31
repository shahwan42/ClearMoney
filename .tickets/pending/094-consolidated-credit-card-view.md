---
id: "094"
title: "Consolidated credit card view"
type: improvement
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Credit card information is scattered across account detail: billing cycle, utilization ring, statement link, and payment history are in separate sections. Consolidate into a single at-a-glance CC dashboard card.

## Acceptance Criteria

- [ ] Single "Credit Card Status" section on account detail for CC accounts
- [ ] Shows in one view: current balance, credit limit, utilization %, billing cycle dates, next due date, minimum payment
- [ ] Utilization ring integrated with balance/limit text (not separate section)
- [ ] "View Statement" and "Pay Bill" actions as primary buttons
- [ ] Payment history summary: last 3 payments with dates and amounts
- [ ] Color-coded utilization: green (<30%), amber (30-70%), red (>70%)
- [ ] Works in both light and dark mode
- [ ] E2E test for CC account detail showing consolidated view

## Technical Notes

- Refactor `backend/accounts/templates/accounts/account_detail.html`
- Data already available via `AccountService.get_statement_data()` and existing context
- No new backend logic — pure template reorganization
- Keep non-CC account detail unchanged (savings, current, cash, prepaid)

## Progress Notes

- 2026-03-31: Created — reduces cognitive load for credit card management
