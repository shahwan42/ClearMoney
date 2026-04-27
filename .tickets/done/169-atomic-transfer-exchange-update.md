---
id: "169"
title: "Atomic transfer/exchange update (both legs + fee)"
type: feature
priority: high
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Current `update()` only touches the one leg the user edited — linked leg stays stale with wrong amount/balance_delta, destination account balance never adjusted. Exchanges have same bug plus rate/counter_amount mismatch.

## Acceptance Criteria

- [x] `update_transfer(tx_id, amount, note, tx_date, fee_amount)` atomically updates both legs + fee in one DB transaction
- [x] `update_exchange(tx_id, amount, rate, counter_amount, note, tx_date)` atomically updates both legs + rate in one DB transaction
- [x] Exchange update logs new `ExchangeRateLog` entry (non-critical)
- [x] View branches on tx type: transfer → `update_transfer`, exchange → `update_exchange`, else → existing `update()`
- [x] HTMX response OOB-swaps both rows after update
- [x] Edit form shows fee_amount field for transfers, rate+counter_amount for exchanges, hides category for both
- [x] All existing tests pass (no regressions)

## Progress Notes

- 2026-04-27: Started — Writing RED tests first, then implementing service methods + view + template
- 2026-04-27: Completed — 15 new tests, update_transfer + update_exchange + _update_fee_in_atomic in transfers.py, view branching, edit form template branching. 1667 tests passing, lint clean.
