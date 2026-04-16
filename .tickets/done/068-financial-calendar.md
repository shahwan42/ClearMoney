---
id: "068"
title: "Financial calendar"
type: feature
priority: medium
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

A monthly calendar view showing upcoming financial events: recurring rule due dates, budget resets, and loan repayment dates.

## Acceptance Criteria

- [ ] New page at `/calendar` with monthly grid view
- [ ] Show recurring rule due dates with amount and type
- [ ] Color-coded by type: expense (red), income (green), transfer (blue)
- [ ] Click day to see/add transactions for that date
- [ ] Month navigation (prev/next) reusing existing reports pattern
- [ ] Show today's date highlighted
- [ ] Responsive: works on mobile (list view fallback for small screens)
- [ ] Service-layer tests for calendar data aggregation
- [ ] E2E test for navigating calendar, clicking a day

## Technical Notes

- New `calendar` app or add to `dashboard` app
- Data sources: `RecurringRule.next_due_date`, `Transaction.date`
- Calendar grid: HTML table with Tailwind styling (no JS calendar library)
- Reuse date navigation from `reports/` templates

## Progress Notes

- 2026-03-31: Created — planned as Tier 2 feature recommendation
