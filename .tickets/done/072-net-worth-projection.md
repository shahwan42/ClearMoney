---
id: "072"
title: "Net worth projection"
type: feature
priority: low
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

Project future net worth based on recurring income/expenses and current spending patterns. "At this rate, you'll have X in savings by December."

## Acceptance Criteria

- [ ] Projection chart on dashboard or reports page showing 3/6/12 month forecast
- [ ] Factor in recurring rules (known future income and expenses)
- [ ] Factor in average discretionary spending from last 3 months
- [ ] Show optimistic/pessimistic/expected scenarios
- [ ] Milestone markers: "You'll reach 100K EGP by [date]"
- [ ] CSS-only chart (extend existing sparkline/bar chart patterns)
- [ ] Service-layer tests for projection calculation with various scenarios
- [ ] E2E test for projection chart rendering with correct data

## Technical Notes

- Build on `DailySnapshot` data for historical trend
- Recurring rules provide known future cash flows
- Discretionary = total spending - recurring expenses (averaged over 3 months)
- Projection: `current_net_worth + Σ(monthly_net_income - monthly_discretionary) * months`
- New service: `ProjectionService` or extend `DashboardService`

## Progress Notes

- 2026-03-31: Created — planned as Tier 3 feature recommendation
