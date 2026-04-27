---
id: "169"
title: "Atomic transfer/exchange update (both legs + fee)"
type: feature
priority: high
status: wip
created: 2026-04-27
updated: 2026-04-27
---

## Description

Current `update()` only touches the one leg the user edited — linked leg stays stale with wrong amount/balance_delta, destination account balance never adjusted. Exchanges have same bug plus rate/counter_amount mismatch.

## Acceptance Criteria

- [ ] `update_transfer(tx_id, amount, note, date, fee_amount)` atomically updates both legs + fee in one DB transaction
- [ ] `update_exchange(tx_id, amount, rate, counter_amount, note, date)` atomically updates both legs + rate in one DB transaction
- [ ] Exchange update logs new `ExchangeRateLog` entry (non-critical)
- [ ] View branches on tx type: transfer → `update_transfer`, exchange → `update_exchange`, else → existing `update()`
- [ ] HTMX response OOB-swaps both rows after update
- [ ] Edit form shows fee_amount field for transfers, rate+counter_amount for exchanges, hides category for both
- [ ] All existing tests pass (no regressions)

## Progress Notes

- 2026-04-27: Started — Writing RED tests first, then implementing service methods + view + template
