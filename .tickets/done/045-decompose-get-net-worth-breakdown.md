---
id: "045"
title: "Decompose get_net_worth_breakdown (100 lines)"
type: refactor
priority: medium
status: done
created: 2026-03-30
updated: 2026-03-30
---

## Description

`get_net_worth_breakdown()` in `dashboard/services/accounts.py` (lines ~138-240) is 100 lines with a large if/elif tree handling 4 different card types (liquid cash, credit used, credit available, investments). Each branch filters accounts differently and transforms balances. Extract per-card-type logic into separate helpers or a strategy dict.

## Acceptance Criteria

- [ ] Extract per-card-type filter and transform logic into helper functions or a strategy mapping
- [ ] Reduce `get_net_worth_breakdown()` to a short orchestrator
- [ ] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
