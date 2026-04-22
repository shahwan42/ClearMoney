---
id: "126"
title: "Dead payment methods: create_instapay_transfer, create_fawry_cashout"
type: chore
priority: medium
status: done
updated: 2026-04-22
---

## Description

Vulture found two transfer service methods that are defined but never called from any view or URL:

- `transactions/services/transfers.py:156` — `create_instapay_transfer`
- `transactions/services/transfers.py:397` — `create_fawry_cashout`

These appear to be payment method integrations (InstaPay, Fawry cashout) that were implemented but never wired to a route.

## Acceptance Criteria

- [x] Confirm neither method is reachable from any URL or called anywhere
- [x] Decision: either wire them up (add views + URLs) or delete them
- [x] If deleted, remove any dead helper code they depend on exclusively
- [x] `make dead` no longer reports them

## Progress Notes

- 2026-04-18: Created — identified by vulture dead code scan
- 2026-04-22: Deleted `create_instapay_transfer`, its helper `calculate_instapay_fee`, and `get_fees_category_id`. Confirmed `create_fawry_cashout` was already gone. Cleaned up docstrings and tests.

