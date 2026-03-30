---
id: "049"
title: "Standardize HTMX error response helpers"
type: refactor
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Views use inconsistent HTTP status codes for similar errors — mix of 400, 422, and sometimes 200 with error HTML. Some views return `HttpResponse(msg, status=400)`, others render templates with `status=422`, others catch bare `Exception`. Consolidate into shared helpers in `core/htmx.py`.

## Affected Files

- `accounts/views.py` — mix of 400/422/404 for validation errors
- `budgets/views.py` — catches `ValueError` + `IntegrityError` differently
- `virtual_accounts/views.py` — inconsistent 400 vs 422
- `categories/views.py` — checks error message string to determine status
- `investments/views.py` — catches bare `Exception`

## Acceptance Criteria

- [ ] Add `validation_error_response(msg)` (422) and `operational_error_response(msg)` (400) to `core/htmx.py`
- [ ] Standardize all views to use these helpers (one app at a time)
- [ ] Document the convention: 422 for validation, 400 for operational, 404 for not found
- [ ] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
