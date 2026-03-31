---
id: "080"
title: "Year-over-year comparison"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Add year-over-year spending comparison to reports. "March 2026 vs March 2025: Food +15%, Transport -20%."

## Acceptance Criteria

- [ ] Reports page: "vs last year" toggle or section
- [ ] Per-category comparison: amount + percentage change
- [ ] Color-coded: green (spending decreased), red (spending increased)
- [ ] Total spending comparison: overall month vs same month last year
- [ ] Handle missing data gracefully (new categories, first year of use)
- [ ] Service-layer tests for YoY calculation with edge cases
- [ ] E2E test for viewing YoY comparison

## Technical Notes

- No new data needed — query transactions for same month, previous year
- Extend `reports/services.py` `get_monthly_report()` or add `get_yoy_comparison()`
- Reuse existing category spending aggregation logic
- Add as new section on reports page with same month navigation

## Progress Notes

- 2026-03-31: Created — extends existing report infrastructure with historical comparison
