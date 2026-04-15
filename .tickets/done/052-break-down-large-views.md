---
id: "052"
title: "Break down large views (account_add, recurring_add)"
type: refactor
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-16
---

## Description

Several views exceed 70+ lines by mixing form parsing, service calls, error handling, and template rendering. The largest offenders should be decomposed by extracting logic into the service layer or into focused helper functions.

## Largest Views

- `account_add` — `accounts/views.py` (~116 lines) — institution resolution, preset JSON serialization, complex error re-rendering
- `recurring_add` — `recurring/views.py` (~102 lines) — template transaction building, fee parsing, multiple validation blocks
- `account_detail` — `accounts/views.py` (~72 lines) — over-allocation warning computation, 10+ data source assembly
- `transaction_update` — `transactions/views.py` (~50 lines) — fee update + VA reallocation mixed in
- `quick_entry_create` — `transactions/views.py` (~52 lines) — duplicates fee/VA allocation from transaction_create

## Acceptance Criteria

- [x] Extract institution resolution from `account_add` into service method
- [x] Extract template transaction building from `recurring_add` into service
- [x] Extract over-allocation warning from `account_detail` into service
- [x] Extract shared fee/VA allocation logic to avoid duplication between `transaction_create` and `quick_entry_create`
- [x] Each view reduced to <50 lines
- [x] All existing tests pass (`make test && make lint && make test-e2e`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
- 2026-04-16: Refactored `account_add`, `account_detail`, `recurring_add`, `transaction_update`, and `quick_entry_create`. Moved logic to `AccountService`, `RecurringService`, and `TransactionService`. All views now < 50 lines. Unit tests passed.
