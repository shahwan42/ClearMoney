---
id: "077"
title: "Fee analytics"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Aggregate transaction fees into a dedicated report. Users don't realize how much they spend on bank transfer fees, ATM fees, and currency conversion fees.

## Acceptance Criteria

- [ ] Fee summary on reports page: total fees this month / this year
- [ ] Breakdown by account (which accounts cost the most in fees)
- [ ] Breakdown by transaction type (transfers vs exchanges vs expenses)
- [ ] Trend: fees over last 6 months
- [ ] "You paid X EGP in fees this year" headline stat
- [ ] Service-layer tests for fee aggregation queries
- [ ] E2E test for viewing fee report with data

## Technical Notes

- `fee_amount` field exists on Transaction model — query with `Sum('fee_amount')`
- Group by account, type, and month for breakdowns
- Add as new section on reports page or new `/reports/fees` route
- No new models needed — pure query + template work

## Progress Notes

- 2026-03-31: Created — leverages existing fee_amount field that's never aggregated
