---
id: "132"
title: "Usage-ordered accounts and categories in transaction forms"
type: improvement
priority: medium
status: done
created: 2026-04-18
updated: 2026-04-18
---

## Description

When creating or editing a transaction (via the quick-entry form or the full transaction page), the account dropdown and category dropdown currently use a fixed ordering (alphabetical or insertion order). Frequent users naturally gravitate toward the same handful of accounts and categories, so the dropdowns should surface the most-used options first, reducing taps and cognitive load.

Both changes apply to **all transaction entry surfaces**:
- Quick-entry (bottom-sheet form)
- Full transaction create/edit page
- Move Money (transfer + exchange) forms — account dropdowns only

## Acceptance Criteria

- [x] **Account dropdown ordered by usage** — accounts with the most transactions (across all types: expense, income, transfer, exchange) appear first; ties broken alphabetically
- [x] **Category dropdown ordered by usage** — categories with the most transactions appear first; applies to both system-seeded and user-created categories
- [x] **Category ordering scoped to user** — usage count is per-user, not global (user A's frequent categories don't affect user B's ordering)
- [x] **Account ordering scoped to user** — same isolation requirement
- [x] **Zero-usage fallback** — accounts/categories with no transactions yet appear at the bottom, still sorted alphabetically among themselves
- [x] **Quick-entry form uses ordered accounts** — uses `get_accounts()` which now annotates with `tx_count`
- [x] **Quick-entry form uses ordered categories** — uses `get_categories()` which uses user-scoped subquery
- [x] **Full transaction page uses ordered accounts** — same `get_accounts()` path
- [x] **Full transaction page uses ordered categories** — same `get_categories()` path
- [x] **Move Money form uses ordered accounts** — `quick_move_money_form` calls `svc.get_accounts()`
- [x] **No N+1 queries** — single annotated queryset with `Count` + `order_by`
- [x] **Unit tests** — `TestDropdownHelpers` + `TestGetForDropdown` cover ordering assertions
- [x] **Data-isolation test** — user B's usage does not affect user A's dropdown order

## Progress Notes

- 2026-04-18: Created — feature request for usage-ordered dropdowns in all transaction entry surfaces
- 2026-04-18: Completed — 4 files changed: `transactions/services/helpers.py` (account Count annotation + user-scoped category subquery), `categories/services.py` (_usage_subquery user-scoped), `accounts/services.py` (get_for_dropdown Count annotation). 8 new tests added. 1479 tests passing.
