---
id: "053"
title: "Standardize error handling conventions across services"
type: refactor
priority: low
status: done
created: 2026-03-30
updated: 2026-04-16
---

## Description

Services handle errors inconsistently — some methods raise `ValueError`, some return `None`, some silently catch and log. Establish and enforce conventions.

## Current Inconsistencies

- `accounts/services.py` — delete wraps in try/except but re-raises
- `budgets/services.py` — update raises `ValueError` for validation
- `recurring/services.py` — `confirm`/`process_due_rules` silently catches exceptions with logging
- `investments/views.py` — catches bare `Exception`
- Some services return `None` for not-found, others raise

## Proposed Conventions

- **CRUD methods**: Raise `ValueError` for validation, let `IntegrityError` bubble, raise `ObjectDoesNotExist` for not-found
- **Batch operations**: Log and continue (partial success is OK)
- **Background jobs**: Always catch, log, and continue

## Acceptance Criteria

- [x] Document the error handling convention in code or rules
- [x] Audit all services and align to the convention
- [x] Remove bare `Exception` catches where possible
- [x] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
- 2026-04-16: Implemented error handling convention in coding-conventions.md

## Changes Made

- Added error handling convention to `.claude/rules/coding-conventions.md`
- `accounts/services.py`: `delete()` now raises `ObjectDoesNotExist` instead of returning error string
- `budgets/services.py`: `update()` now raises `ObjectDoesNotExist` for not-found
- `categories/services.py`: `archive()` now raises `ObjectDoesNotExist` for not-found
- Updated callers in `accounts/views.py`, `budgets/views.py`, `settings_app/views.py`
- Updated tests to expect `ObjectDoesNotExist` instead of `ValueError` for not-found cases

## Notes on Bare Exception Catches

The bare `except Exception` catches found in batch/background operations (e.g., `dashboard/services/__init__.py`, `push/services.py`, `jobs/*`) are intentional per the convention — these are aggregation services where partial failure is acceptable.
