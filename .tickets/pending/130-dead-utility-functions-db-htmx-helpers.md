---
id: "130"
title: "Dead utility functions: row_to_dict, rows_to_dicts, success_response, _lookup_account_currency"
type: chore
priority: low
status: pending
created: 2026-04-18
updated: 2026-04-18
---

## Description

Vulture found four utility functions never called anywhere:

- `core/db.py:10` — `row_to_dict`
- `core/db.py:33` — `rows_to_dicts`
- `core/htmx.py:209` — `success_response`
- `recurring/views.py:80` — `_lookup_account_currency` (private helper)

## Acceptance Criteria

- [ ] Confirm each is unreachable (grep across codebase)
- [ ] Delete confirmed-dead functions
- [ ] `make dead` no longer reports them

## Progress Notes

- 2026-04-18: Created — identified by vulture dead code scan
