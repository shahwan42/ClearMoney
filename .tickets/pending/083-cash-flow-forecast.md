---
id: "083"
title: "Cash flow forecast"
type: feature
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Forecast account balances based on known recurring income/expenses. "You have 15,000 EGP. With known flows, you'll have 19,000 by month-end."

## Acceptance Criteria

- [ ] Dashboard card or dedicated page showing projected balance at end of month
- [ ] Factor in all active recurring rules (income and expenses) with due dates
- [ ] Show daily projected balance as a stepped line (balance after each expected event)
- [ ] Warning when projected balance goes negative
- [ ] "What if" toggle: include/exclude specific recurring rules
- [ ] Service-layer tests for forecast calculation with multiple rules and dates
- [ ] E2E test for viewing forecast with recurring rules configured

## Technical Notes

- Data source: `RecurringRule` model has `next_due_date`, `template_transaction` (amount, type)
- Iterate through remaining days in month, apply rules on their due dates
- Start with current account balances, add/subtract expected transactions
- New service: `ForecastService` or extend `DashboardService`
- CSS-only stepped chart or extend existing sparkline pattern

## Progress Notes

- 2026-03-31: Created — uses existing recurring rules as future cash flow predictions
