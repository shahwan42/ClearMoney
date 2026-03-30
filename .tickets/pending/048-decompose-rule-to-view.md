---
id: "048"
title: "Decompose rule_to_view (84 lines)"
type: refactor
priority: low
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

`rule_to_view()` in `recurring/services.py` (lines ~307-383) is 84 lines handling polymorphic input (dict vs dataclass) with duplicated field extraction and mixed concerns (view formatting + data fetching). Simplify by standardizing input and separating concerns.

## Acceptance Criteria

- [ ] Standardize on one input type (convert dicts to dataclass in caller)
- [ ] Extract account name lookup to a separate method
- [ ] Extract template formatting to a simple transformation function
- [ ] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
