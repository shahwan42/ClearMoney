---
id: "176"
title: "Fix transfer/exchange transaction colors"
type: bug
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Deposited transfer/exchange transactions show blue (`text-blue-600`) instead of green (`text-green-600`). Withdrawn transfers show correct red in `display.py` but neutral slate in `crud.py` HTMX responses. Two code paths disagree.

Desired: red for withdrawn (negative delta), green for deposited (positive delta), blue dot indicator for both — distinguishes transfers from expenses/income visually.

## Acceptance Criteria

- [x] `display.py`: positive transfer/exchange returns `text-green-600`
- [x] `crud.py`: uses `display.py` functions (single source of truth)
- [x] `crud.py`: transfer indicator uses blue (`#60a5fa`), not slate
- [x] All existing tests updated/pass

## Progress Notes

- 2026-04-27: Started — fixing display.py and unifying crud.py color logic
- 2026-04-27: Completed — display.py positive branch → green, crud.py delegates to display.py, 1722 tests pass
