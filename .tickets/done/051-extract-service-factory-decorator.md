---
id: "051"
title: "Extract service factory decorator from views"
type: refactor
priority: low
status: done
created: 2026-03-30
updated: 2026-04-16
---

## Description

Every `views.py` file contains a `_svc(request)` helper function that instantiates the app's service class with `request.user_id` and `request.tz`. This pattern is duplicated ~10 times across all apps. Extract into a reusable decorator or helper in `core/`.

## Duplicated Locations

- `transactions/views.py`, `accounts/views.py`, `virtual_accounts/views.py`, `budgets/views.py`, `recurring/views.py`, `investments/views.py`, `people/views.py`, `settings_app/views.py`, `categories/views.py`, `exchange_rates/views.py`

## Acceptance Criteria

- [x] Create `core/decorators.py` with `@inject_service(ServiceClass)` or similar pattern
- [x] Replace `_svc()` helpers in all views incrementally
- [x] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
- 2026-04-16: Completed — Implemented @inject_service decorator in core/decorators.py with comprehensive documentation. Updated all 7 view files (transactions, budgets, categories, investments, people, recurring, virtual_accounts) to use the new decorator. Also updated VirtualAccountService to accept optional tz parameter for API consistency. All 1354 tests passing.
