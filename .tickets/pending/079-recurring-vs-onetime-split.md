---
id: "079"
title: "Recurring vs one-time spending split"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Show users what percentage of their spending is fixed/recurring vs discretionary/one-time. Helps identify what they can actually control and cut.

## Acceptance Criteria

- [ ] Reports section: "65% fixed, 35% discretionary" with visual split bar
- [ ] Recurring = transactions with `recurring_rule_id` set
- [ ] Discretionary = transactions without `recurring_rule_id`
- [ ] Breakdown by category within each group
- [ ] Trend over 3-6 months (is discretionary spending growing?)
- [ ] Service-layer tests for split calculation
- [ ] E2E test for viewing split on reports page

## Technical Notes

- Transaction model has `recurring_rule_id` FK — null means one-time, set means recurring
- Query: two `Sum` annotations filtered by `recurring_rule_id__isnull=True/False`
- Add to existing reports page as new section
- No new models needed — pure query work

## Progress Notes

- 2026-03-31: Created — leverages existing recurring_rule_id FK on transactions
