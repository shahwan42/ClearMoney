---
id: "076"
title: "Spending velocity projections"
type: feature
priority: high
status: done
created: 2026-03-31
updated: 2026-04-17
---

## Description

Surface existing SpendingVelocity computation as actionable daily budget advice. Show users how much they can spend per remaining day to stay on budget.

## Acceptance Criteria

- [x] Dashboard card: "Daily budget remaining: X EGP/day for Y days"
- [x] Projected month-end spend: "At this pace, you'll spend X vs budget of Y"
- [x] Color-coded: green (on track), amber (at risk), red (will overspend)
- [x] Per-category velocity for budgeted categories
- [x] Actionable advice: "Reduce by Z/day to stay on track" when amber/red
- [x] Service-layer tests for projection math with various scenarios
- [x] E2E test for dashboard card showing velocity data

## Technical Notes

- `SpendingVelocity` already computed in `dashboard/services/spending.py` (line 35-43, 150-157)
- Currently shows status but no projections — extend with: projected_total = (spent / elapsed_days) * total_days
- daily_remaining = (budget - spent) / remaining_days
- Add to dashboard context and template; no new models needed

## Implementation Summary

### Files Changed

**`backend/dashboard/services/spending.py`**
- Extended `SpendingVelocity` dataclass with 6 new projection fields:
  `daily_pace`, `budget_daily`, `daily_remaining`, `projected_total`, `budget_total`, `reduce_by`
- Added `CategoryVelocity` dataclass for per-category spending velocity
- Added `compute_category_velocities()` function that reads active budgets via `BudgetService`
  and computes per-category projection math
- Updated `compute_spending_comparison()` to populate all new `SpendingVelocity` fields
- Guard: `daily_remaining = 0` when `budget_total = 0` (no last-month baseline)

**`backend/dashboard/services/__init__.py`**
- Imported and exported `CategoryVelocity` and `compute_category_velocities`
- Added `category_velocities` field to `DashboardData`
- Wired `_compute_category_velocities()` call in `_load_activity_data()` (step 18)
- Added `_compute_category_velocities()` delegate method to `DashboardService`

**`backend/dashboard/templates/dashboard/_spending.html`**
- Replaced the simple velocity bar with a full projections card:
  - Daily budget remaining text with ID `#daily-budget-remaining`
  - Projected spend vs last month text with ID `#projected-spend`
  - Color-coded status badge (`#velocity-status-badge`) — On Track / At Risk / Overspending
  - Actionable advice (`#velocity-advice`) when amber/red: "Reduce by X/day to stay on track"
  - Per-category velocity rows (`#category-velocity-list`) with mini progress bars
  - All sections have stable HTML IDs for E2E targeting

**`backend/dashboard/tests/test_services.py`**
- Added `from core.dates import prev_month_range` import
- Added 10 new tests covering:
  - On-track spending (green, daily_remaining > 0, reduce_by = 0)
  - `projected_total` formula accuracy
  - `daily_remaining` formula accuracy
  - Overspend triggers `reduce_by > 0` and amber/red status
  - No last-month baseline → safe zero values
  - No spending at all → all fields zero
  - Category velocities: basic, over-budget, no budgets, dashboard context

**`e2e/tests/test_dashboard.py`**
- Added `_create_budget_via_sql()` helper
- Added `TestSpendingVelocityCard` class with 4 E2E tests:
  - `test_velocity_section_visible_with_spending`
  - `test_velocity_card_shows_daily_budget`
  - `test_velocity_status_badge_visible`
  - `test_category_velocity_section_with_budget`

## Progress Notes

- 2026-03-31: Created — surfaces existing underutilized computation
- 2026-04-17: Implemented — extended SpendingVelocity with projection math, added CategoryVelocity,
  updated dashboard template with actionable daily budget advice card, per-category velocity rows,
  color-coded status, and advice text. All 127 dashboard unit tests pass.
