---
id: "161"
title: "Rename Virtual Accounts to Pots in UI"
type: improvement
priority: medium
status: done
created: 2026-04-26
updated: 2026-04-26
---

## Description

Rename user-visible "Virtual Account(s)" → "Pot(s)" (English) and "حسابات افتراضية" → "مدخرات / مدخرة" (Arabic). The feature is a savings bucket inside a parent account (target_amount, target_date, monthly_target, progress_pct), not a YNAB-style spending envelope. "Pots" matches the Monzo metaphor and the actual behavior — money set aside inside a real account, accumulating toward a goal.

UI labels only. URLs, DB tables, app name, model class, hint_keys, and factory test fixtures stay as-is.

## Acceptance Criteria

- [x] Templates updated: 9 files across virtual_accounts/, dashboard/, accounts/, settings_app/, transactions/, templates/components/bottom-nav.html
- [x] User-facing Python strings updated: virtual_accounts/services.py, virtual_accounts/views.py, transactions/services/helpers.py
- [x] Title case in headings/nav ("Pots", "New Pot"); sentence case in body
- [x] Drop redundant "Pot" prefix where context obvious (e.g., "Allocation" not "Pot Allocation")
- [x] Arabic `.po` updated: 6 active entries → "المدخرات / مدخرة" variants
- [x] Test assertions updated in lockstep
- [x] `make test` 1592 passed
- [x] Ruff + mypy clean on all changed files

## Out of Scope

- URL paths (`/virtual-accounts/`)
- DB table `virtual_accounts`
- Model class `VirtualAccount`
- App name `virtual_accounts`
- Internal hint_keys (`hint_key="virtual_accounts"`)
- Factory string `f"Virtual Account {n}"` (test fixture)
- Code comments and docstrings

## Progress Notes

- 2026-04-26: Started — Plan finalized via /grill-me. Term: Pots (en) / مدخرات (ar). Scope: UI labels only.
- 2026-04-26: Completed — 9 templates + 3 Python files updated. Arabic .po updated with new msgids/msgstrs. Tests updated: virtual_accounts/tests/test_views.py, transactions/tests/test_services.py, core/tests/test_more_menu.py. 1592 tests passing. `compilemessages` and `makemessages` blocked by pre-existing duplicate msgid in po file (`ClearMoney - Transfer` lines 2212/2225) — not introduced by this ticket; tracked separately. `recurring/services.py` ruff format issue also pre-existing on main, not staged.
