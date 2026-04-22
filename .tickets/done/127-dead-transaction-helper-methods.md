id: "127"
title: "Dead transaction helper methods: get_fees_category_id, get_recent, get_by_account"
type: chore
priority: low
status: done
created: 2026-04-18
updated: 2026-04-22
---

## Description

Vulture found three methods in `transactions/services/helpers.py` that are defined but never called:

- `:324` — `get_fees_category_id` (removed in commit c33cb3aa)
- `:393` — `get_recent`
- `:519` — `get_by_account`

## Acceptance Criteria

- [x] Confirm none are called anywhere (grep + check views/templates)
- [x] Delete if confirmed dead
- [x] `make dead` no longer reports them

## Progress Notes

- 2026-04-18: Created — identified by vulture dead code scan
- 2026-04-22: `get_fees_category_id` already removed in previous commit. Removed `get_recent` and `get_by_account` (and their helper `_dict_from_values` and `_BARE_TX_COLS`). Verified with `make dead` and tests.
