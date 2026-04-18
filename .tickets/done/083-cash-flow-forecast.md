---
id: "083"
title: "Cash flow forecast"
type: feature
priority: high
status: done
created: 2026-03-31
updated: 2026-04-18
---

## Description

Forecast account balances based on known recurring income/expenses. "You have 15,000 EGP. With known flows, you'll have 19,000 by month-end."

## Acceptance Criteria

- [x] Dashboard card or dedicated page showing projected balance at end of month
- [x] Factor in all active recurring rules (income and expenses) with due dates
- [x] Show daily projected balance as a stepped line (balance after each expected event)
- [x] Warning when projected balance goes negative
- [x] "What if" toggle: include/exclude specific recurring rules
- [x] Service-layer tests for forecast calculation with multiple rules and dates
- [x] E2E test for viewing forecast with recurring rules configured

## Technical Notes

- Data source: `RecurringRule` model has `next_due_date`, `template_transaction` (amount, type)
- Iterate through remaining days in month, apply rules on their due dates
- Start with current account balances, add/subtract expected transactions
- New service: `ForecastService` or extend `DashboardService`
- CSS-only stepped chart or extend existing sparkline pattern

## Progress Notes

- 2026-03-31: Created — uses existing recurring rules as future cash flow predictions
- 2026-04-18: Implemented
  - Created `ForecastService` in `dashboard/services/forecast.py`
  - Added forecast calculation with daily breakdown
  - Integrated into `DashboardService` and dashboard template
  - Created `_cash_flow_forecast.html` partial with summary and mini chart
  - Added 17 service-layer tests covering all scenarios
  - Added 2 E2E tests for forecast visibility and warnings
  - All tests passing
