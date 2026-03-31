---
id: "093"
title: "Interactive report charts with drill-down"
type: improvement
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Donut and bar charts on the reports page are display-only. Make chart segments clickable to drill into transactions for that category or month. Convert currency filter from page reload to HTMX.

## Acceptance Criteria

- [ ] Donut chart segments are clickable — clicking a category filters transaction list below
- [ ] Bar chart bars are clickable — clicking a month navigates to that month's report
- [ ] Hover/focus shows tooltip with category name + amount + percentage
- [ ] Currency filter uses HTMX (`hx-get`) instead of `location.href` page reload
- [ ] Transaction list appears below chart when segment clicked (HTMX partial load)
- [ ] "Clear filter" button to reset drill-down
- [ ] Keyboard accessible: Tab to segments, Enter to drill-down
- [ ] E2E test for clicking chart segment → transactions filtered

## Technical Notes

- Donut chart uses CSS `conic-gradient` — add invisible clickable overlay `<a>` elements positioned over each segment
- Bar chart uses flexbox — each bar already a `<div>`, add `onclick` or wrap in `<a>`
- Currency filter: change `onchange="location.href=..."` to `hx-get` with `hx-target`
- New endpoint: `GET /reports/transactions?category_id=X&month=Y` returning HTML partial
- Template: `backend/templates/reports/reports.html`

## Progress Notes

- 2026-03-31: Created — makes reports actionable instead of display-only
