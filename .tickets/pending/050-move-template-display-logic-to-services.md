---
id: "050"
title: "Move template display logic to services"
type: refactor
priority: low
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Color thresholds, progress bar capping, and utilization color logic are hardcoded in templates instead of being computed in the service/view layer. This makes the logic untestable and duplicated.

## Locations

- `accounts/templates/accounts/account_detail.html` — credit utilization color thresholds (>80% red, >50% amber)
- `accounts/templates/accounts/account_detail.html` — balance color (negative = red)
- `accounts/templates/accounts/account_detail.html` — VA progress bar width capped at 100%
- `transactions/templates/transactions/_transaction_row.html` — type-based color/icon logic

## Acceptance Criteria

- [ ] Compute utilization color in service, pass as context variable
- [ ] Compute balance color class in service or template filter
- [ ] Cap VA progress percentage in service (not template)
- [ ] Templates only reference pre-computed display values
- [ ] All existing tests pass (`make test && make lint && make test-e2e`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
