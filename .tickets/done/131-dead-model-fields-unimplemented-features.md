---
id: "131"
title: "Dead model fields from unimplemented features: rollover_amount, is_system, is_archived, VALID_CATEGORY_TYPES"
type: chore
priority: low
status: done
created: 2026-04-18
updated: 2026-04-18
---

## Description

Vulture found schema and type fields that are declared but never read. Research confirmed several are true positives (dead code), while others are false positives (used in templates or via dict access).

### Confirmed Dead (To Delete)
- `categories/services.py:28` — `VALID_CATEGORY_TYPES` constant
- `investments/models.py:39` — `valuation` method (service layer computes it manually)
- `accounts/display.py:71` — `cap_progress_percentage` display helper
- `accounts/institution_data.py:289` — `is_image_icon` (duplicate of template filter)
- `accounts/models.py:81` / `accounts/types.py:46` — `role_tags` field

### False Positives (To Whitelist)
- `budgets/types.py:29` — `rollover_amount` (Used in templates)
- `categories/models.py:27` — `is_system` (Used in service layer protection logic)
- `categories/models.py:28` — `is_archived` (Used for soft-delete)
- `virtual_accounts/models.py:45` — `is_archived` (Used for soft-delete)
- `accounts/models.py:91/94/97` — `last_checked_balance`, etc. (Used via `.update()`)

## Acceptance Criteria

- [x] Research usage of all listed items
- [ ] Delete confirmed dead code
- [ ] Consolidate `is_image_icon` to use `core.templatetags.money` version
- [ ] Create migration to drop `role_tags` column
- [ ] Update `vulture_whitelist.py` to silence false positives
- [ ] `make dead` no longer reports these items

## Implementation Plan

1.  **Whitelisting**: Add false positives to `backend/vulture_whitelist.py`.
2.  **Simple Deletions**: Remove `VALID_CATEGORY_TYPES`, `cap_progress_percentage`, `valuation`.
3.  **Consolidation**: Replace `is_image_icon` in `institution_data.py` with import or just remove it if tests can be updated.
4.  **Schema Change**: Remove `role_tags` from `Account` model and `AccountSummary` type, create migration.
5.  **Verification**: Run `make dead` and `make test`.

## Progress Notes

- 2026-04-18: Created — identified by vulture dead code scan
