---
id: "076"
title: "Spending velocity projections"
type: feature
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Surface existing SpendingVelocity computation as actionable daily budget advice. Show users how much they can spend per remaining day to stay on budget.

## Acceptance Criteria

- [ ] Dashboard card: "Daily budget remaining: X EGP/day for Y days"
- [ ] Projected month-end spend: "At this pace, you'll spend X vs budget of Y"
- [ ] Color-coded: green (on track), amber (at risk), red (will overspend)
- [ ] Per-category velocity for budgeted categories
- [ ] Actionable advice: "Reduce by Z/day to stay on track" when amber/red
- [ ] Service-layer tests for projection math with various scenarios
- [ ] E2E test for dashboard card showing velocity data

## Technical Notes

- `SpendingVelocity` already computed in `dashboard/services/spending.py` (line 35-43, 150-157)
- Currently shows status but no projections — extend with: projected_total = (spent / elapsed_days) * total_days
- daily_remaining = (budget - spent) / remaining_days
- Add to dashboard context and template; no new models needed

## Progress Notes

- 2026-03-31: Created — surfaces existing underutilized computation
