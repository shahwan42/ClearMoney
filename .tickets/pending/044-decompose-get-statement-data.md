---
id: "044"
title: "Decompose get_statement_data (133 lines)"
type: refactor
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

`AccountService.get_statement_data()` in `accounts/services.py` (lines ~636-768) is 133 lines long, mixing period parsing, transaction filtering, balance calculation, interest-free period logic, and payment history in one function. Break into focused sub-functions.

## Acceptance Criteria

- [ ] Extract `_parse_statement_period(period_str, statement_day, due_day)` — period date parsing
- [ ] Extract `_fetch_statement_transactions(user_id, account_id, start, end)` — query logic
- [ ] Extract `_calculate_opening_balance(transactions, closing_balance)` — arithmetic
- [ ] Extract `_calculate_interest_free_period(period_end, today)` — date logic
- [ ] Extract `_fetch_payment_history(user_id, account_id)` — payment query
- [ ] Compose all in a shorter `get_statement_data()` orchestrator
- [ ] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
