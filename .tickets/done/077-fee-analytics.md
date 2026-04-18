---
id: "077"
title: "Fee analytics"
type: feature
priority: medium
status: done
updated: 2026-04-18
---

## Description

Aggregate transaction fees into a dedicated report. Users don't realize how much they spend on bank transfer fees, ATM fees, and currency conversion fees.

## Acceptance Criteria

- [x] Fee summary on reports page: total fees this month / this year
- [x] Breakdown by account (which accounts cost the most in fees)
- [x] Breakdown by transaction type (transfers vs exchanges vs expenses)
- [x] Trend: fees over last 6 months
- [x] "You paid X EGP in fees this year" headline stat
- [x] Service-layer tests for fee aggregation queries
- [x] E2E test for viewing fee report with data

## Technical Notes

- Leverages standard "Fees & Charges" category for aggregation.
- Determines fee type via linked transaction or note parsing (Transfer/InstaPay/Exchange/Fawry).
- Added as new section on reports page.
- No new models needed.

## Progress Notes

- 2026-03-31: Created — leverages existing fee_amount field that's never aggregated
- 2026-04-18: Implemented fee analytics service, template partial, and tests. Note: fee_amount field was removed from model, so category-based aggregation is used instead.
