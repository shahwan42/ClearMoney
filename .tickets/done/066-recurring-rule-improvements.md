---
id: "066"
title: "Recurring rule improvements"
type: improvement
priority: medium
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

Extend recurring rules with more frequencies, expected-vs-actual tracking, and a calendar view of upcoming transactions.

## Acceptance Criteria

- [ ] New frequencies: biweekly, quarterly, yearly (add to `frequency` choices)
- [ ] Expected vs. actual tracking: after confirming, compare template amount with actual transaction amount
- [ ] Calendar view: monthly calendar showing upcoming recurring transaction due dates
- [ ] Color-coded by type: expense (red), income (green), transfer (blue)
- [ ] Click day to see due rules and optionally confirm them
- [ ] Push notification when a recurring rule is due (integrate with `NotificationService`)
- [ ] Service-layer tests for new frequencies, date calculations, expected-vs-actual
- [ ] E2E test for creating yearly rule, viewing calendar, confirming from calendar

## Technical Notes

- Extend `frequency` CharField choices (currently 'monthly', 'weekly')
- Date calculation for biweekly: `next_due_date + timedelta(weeks=2)`
- Quarterly: `next_due_date + relativedelta(months=3)`
- Yearly: `next_due_date + relativedelta(years=1)`
- Calendar view: new template partial, reuse existing date navigation from reports

## Progress Notes

- 2026-03-31: Created — planned as Tier 2 feature recommendation
