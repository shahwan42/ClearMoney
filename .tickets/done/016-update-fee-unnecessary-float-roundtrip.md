---
id: "016"
title: "update_fee_for_transaction unnecessary Decimal→float→Decimal round-trip"
type: improvement
priority: low
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

In `crud.py` `update_fee_for_transaction()`, when creating a new fee it calls `create_fee_for_transaction(fee_amount=float(new_fee))` where `new_fee` is already a `Decimal`. This performs an unnecessary `Decimal → float → Decimal(str(float))` round-trip. No precision loss in practice for 2-decimal monetary values, but it contradicts the project's "no float arithmetic" convention.

## Acceptance Criteria

- [x] `update_fee_for_transaction` passes Decimal directly without float conversion
- [x] `create_fee_for_transaction` signature accepts `Decimal | float` or just `Decimal`

## Progress Notes

- 2026-03-28: Created — found during QA of Ticket #012
- 2026-03-28: Completed — removed float() wrapper, updated signature to Decimal | float
