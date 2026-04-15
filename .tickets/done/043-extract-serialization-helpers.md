---
id: "043"
title: "Extract serialization helpers to core/serializers.py"
type: refactor
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-15
---

## Description

Row-to-dict conversion functions with UUID stringification and Decimal→float conversion are reimplemented in 6+ services. Each has its own `_row_to_dict()` / `_instance_to_dict()` with near-identical boilerplate. Extract shared helpers.

## Duplicated Locations

- `accounts/services.py` — `_parse_jsonb` (lines ~70-81)
- `people/services.py` — `_person_to_dict`, `_person_instance_to_dict`, `_tx_to_dict`, `_tx_instance_to_dict` (lines ~32-92)
- `virtual_accounts/services.py` — `_row_to_va`, `_instance_to_va` (lines ~48-100)
- `recurring/services.py` — `_row_to_rule`, `_instance_to_rule` (lines ~47-88)
- `categories/services.py` — `_instance_to_dict`, `_row_to_dict` (lines ~40-69)
- `exchange_rates/services.py` — inline dict conversion in `get_all()` (lines ~33-47)

## Acceptance Criteria

- [x] Create `backend/core/serializers.py` with generic `serialize_row(row, field_defs)` and `serialize_instance(instance, fields)` helpers
- [x] Helpers handle UUID→str, Decimal→float, and optional field mapping
- [x] Replace per-service conversion functions incrementally (one service at a time)
- [x] Add unit tests for serialization edge cases (None values, nested fields)
- [x] All existing tests pass (`make test && make lint`)

## Progress Notes

- 2026-03-30: Created — identified from codebase-wide refactoring audit
- 2026-04-15: Completed — created core/serializers.py, replaced helpers in 6 services, 31 new tests pass, all 1309 tests pass
