---
id: "138"
title: "Fix balance check JS diff calculation with locale-sensitive number rendering"
type: bug
priority: high
status: done
created: 2026-04-20
updated: 2026-04-23
---

## Description

The balance check page embeds `{{ account.current_balance }}` and `{{ entered_balance }}` into JavaScript `parseFloat("...")` calls. With `USE_L10N = True` and Arabic locale active, Django formats these floats with a comma as the decimal separator (e.g., `"3118,1"`). JavaScript's `parseFloat` stops at the comma, returning only the integer part (`3118`), causing wrong difference calculations.

## Acceptance Criteria

- [x] JS `currentBalance` always reflects the exact DB value regardless of active locale
- [x] JS `initialBalance` always reflects the exact entered balance regardless of locale
- [x] Difference shown to user is correct in both English and Arabic locale
- [x] No regression in existing balance check tests

## Progress Notes

- 2026-04-20: Started — fixing locale-sensitive float rendering in balance_check.html
- 2026-04-23: Completed — verified `balance_check.html` already emits locale-neutral JS numeric literals via `stringformat:"g"`, added an Arabic-locale regression test for `currentBalance` and `initialBalance`, and reran the affected accounts view tests successfully
