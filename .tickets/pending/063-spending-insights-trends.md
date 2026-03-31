---
id: "063"
title: "Spending insights and trends"
type: feature
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Add trend analysis and anomaly detection to the reports page. Show category spending trends over 3/6/12 months, savings rate, and spending anomalies.

## Acceptance Criteria

- [ ] Category trend view: sparkline per category showing 3/6/12 month spending history
- [ ] Anomaly callouts: "You spent X% more on [category] vs your 3-month average"
- [ ] Top 3 growing expense categories highlighted
- [ ] Monthly savings rate: `(income - expenses) / income` as percentage with trend
- [ ] Period selector: 3m / 6m / 12m toggle
- [ ] CSS-only charts (extend existing SVG sparkline pattern, no Chart.js)
- [ ] Service-layer tests for trend calculation, anomaly detection, savings rate
- [ ] E2E test for navigating to insights, verifying data renders

## Technical Notes

- Build on existing `reports/services.py` — extend `get_monthly_history()` for multi-month data
- Anomaly threshold: flag categories where current month > 130% of rolling average
- Savings rate uses same income/expense aggregation as existing month summary
- New template section on reports page or new `/reports/insights` route

## Progress Notes

- 2026-03-31: Created — planned as Tier 1 feature recommendation
