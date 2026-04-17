---
id: "127"
title: "Dead transaction helper methods: get_fees_category_id, get_recent, get_by_account"
type: chore
priority: low
status: pending
created: 2026-04-18
updated: 2026-04-18
---

## Description

Vulture found three methods in `transactions/services/helpers.py` that are defined but never called:

- `:324` — `get_fees_category_id`
- `:393` — `get_recent`
- `:519` — `get_by_account`

## Acceptance Criteria

- [ ] Confirm none are called anywhere (grep + check views/templates)
- [ ] Delete if confirmed dead
- [ ] `make dead` no longer reports them

## Progress Notes

- 2026-04-18: Created — identified by vulture dead code scan
