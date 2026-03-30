---
id: "053"
title: "Standardize error handling conventions across services"
type: refactor
priority: low
status: pending
created: 2026-03-30
updated: 2026-03-30
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

- [ ] Document the error handling convention in code or rules
- [ ] Audit all services and align to the convention
- [ ] Remove bare `Exception` catches where possible
- [ ] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
