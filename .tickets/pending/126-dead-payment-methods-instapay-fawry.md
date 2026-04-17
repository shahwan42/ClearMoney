---
id: "126"
title: "Dead payment methods: create_instapay_transfer, create_fawry_cashout"
type: chore
priority: medium
status: pending
created: 2026-04-18
updated: 2026-04-18
---

## Description

Vulture found two transfer service methods that are defined but never called from any view or URL:

- `transactions/services/transfers.py:156` — `create_instapay_transfer`
- `transactions/services/transfers.py:397` — `create_fawry_cashout`

These appear to be payment method integrations (InstaPay, Fawry cashout) that were implemented but never wired to a route.

## Acceptance Criteria

- [ ] Confirm neither method is reachable from any URL or called anywhere
- [ ] Decision: either wire them up (add views + URLs) or delete them
- [ ] If deleted, remove any dead helper code they depend on exclusively
- [ ] `make dead` no longer reports them

## Progress Notes

- 2026-04-18: Created — identified by vulture dead code scan
