---
id: "051"
title: "Extract service factory decorator from views"
type: refactor
priority: low
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Every `views.py` file contains a `_svc(request)` helper function that instantiates the app's service class with `request.user_id` and `request.tz`. This pattern is duplicated ~10 times across all apps. Extract into a reusable decorator or helper in `core/`.

## Duplicated Locations

- `transactions/views.py`, `accounts/views.py`, `virtual_accounts/views.py`, `budgets/views.py`, `recurring/views.py`, `investments/views.py`, `people/views.py`, `settings_app/views.py`, `categories/views.py`, `exchange_rates/views.py`

## Acceptance Criteria

- [ ] Create `core/decorators.py` with `@inject_service(ServiceClass)` or similar pattern
- [ ] Replace `_svc()` helpers in all views incrementally
- [ ] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
