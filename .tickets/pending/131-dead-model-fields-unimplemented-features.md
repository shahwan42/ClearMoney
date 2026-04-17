---
id: "131"
title: "Dead model fields from unimplemented features: rollover_amount, is_system, is_archived, VALID_CATEGORY_TYPES"
type: chore
priority: low
status: pending
created: 2026-04-18
updated: 2026-04-18
---

## Description

Vulture found schema and type fields that are declared but never read:

- `budgets/types.py:29` — `rollover_amount` in a TypedDict (budget rollover never implemented)
- `categories/models.py:27` — `is_system` DB column
- `categories/models.py:28` — `is_archived` DB column
- `categories/services.py:28` — `VALID_CATEGORY_TYPES` constant
- `virtual_accounts/models.py:45` — `is_archived` DB column

Also in this batch:
- `investments/models.py:39` — `valuation` method on Investment model, never called
- `accounts/display.py:71` — `cap_progress_percentage`, display helper never called
- `accounts/institution_data.py:289` — `is_image_icon`, utility function (also a template tag in money.py — may be a duplicate)
- `accounts/models.py:81` / `accounts/types.py:46` — `role_tags` field declared in both model and TypedDict

## Acceptance Criteria

- [ ] For each: confirm unused via grep, then either delete or wire up
- [ ] `is_system` / `is_archived` / `is_archived` (VA) — if dropping DB columns, use multi-step migration
- [ ] `make dead` no longer reports them

## Progress Notes

- 2026-04-18: Created — identified by vulture dead code scan
