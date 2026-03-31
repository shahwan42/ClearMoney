---
id: "055"
title: "Transaction helpers test coverage"
type: test
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

`transactions/services/helpers.py` has the **lowest coverage in the codebase at 74.58%** (30 uncovered lines). Key untested paths include VA validation, fees category lookup fallback, category type filtering, limit boundary conditions, and type conversion edge cases.

## Acceptance Criteria

- [ ] Test VA-not-found raises ValueError (line 145)
- [ ] Test TX-not-found raises ValueError (line 150)
- [ ] Test account linkage mismatch between VA and TX (line 153)
- [ ] Test `get_fees_category_id()` returns None when "Fees & Charges" category missing (lines 278-285)
- [ ] Test `get_categories()` with `cat_type` parameter (line 238)
- [ ] Test `get_recent()` with limit=0 and limit=-1 (lines 354-362)
- [ ] Test `get_by_account()` filters correctly (lines 366-375)
- [ ] Test `_dict_from_values()` handles UUID, Decimal, tag arrays (lines 321-347)
- [ ] Coverage of helpers.py reaches at least 90%
- [ ] All existing tests still pass

## Files

- `backend/transactions/services/helpers.py` — target file
- `backend/transactions/tests/test_services.py` — add new test classes

## Estimated Size

Medium — 8-10 new tests, no code changes needed.

## Progress Notes

- 2026-03-31: Created — identified as lowest coverage file during test coverage analysis
