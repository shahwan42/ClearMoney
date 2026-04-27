---
id: "511"
title: "Institution edit — system bank combobox"
type: feature
priority: high
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Extend the institution edit form to include the same system bank combobox from Ticket #510. Users can link an existing institution to a system bank (or change/remove the link). When an institution is already linked, the combobox shows the current system bank pre-selected.

## UX Flow

1. User opens edit form for an existing institution
2. Combobox pre-populated with current `system_bank` (if set) showing its SVG logo + name
3. User can search and select a different system bank, or clear the selection (revert to custom name)
4. "Clear" option in combobox removes the FK and restores editable name field
5. Saving updates `system_bank_id` and name accordingly

## Form Changes

- Combobox pre-populated from `institution.system_bank` FK
- "Clear bank selection" link below combobox to unlink
- When unlinked: name field becomes editable again (text input)
- When linked: name field shows system bank's current-language name (read-only, driven by FK)

## Service Changes

Institution service `update()` updated to:
- Accept `system_bank_id` param (can be empty string to clear)
- Set `system_bank_id = None` when cleared
- Keep existing `name` field value for unlinked institutions

## Acceptance Criteria

- [x] Edit form `<select>` pre-selects current `system_bank_id` when set
- [x] Edit form shows "Custom (no linked bank)" option selected when FK null
- [x] Selecting a system bank in the dropdown updates the FK on submit (verified via HTTP test)
- [x] Selecting "Custom" (empty value) clears the FK
- [x] `InstitutionService.update()` handles `system_bank_id` param (already added in #509; sentinel preserves FK when arg omitted)
- [x] RTL layout: native `<select>` is fully RTL-aware via Tailwind `start-/end-` utilities
- [x] HTTP-level tests: 4 cases — pre-select on edit, custom-shown when null, link via update, clear via update
- [~] E2E test: SKIPPED for the same reason as #510 — institution edit form is not on the visible user-facing path. HTTP tests cover the full request/response cycle.
- [x] `make test && make lint` pass — 1815 tests, ruff + mypy clean

## Affected User Journeys

- J-3 (Account Management): editing an institution can now link/unlink a SystemBank.

## Deviations from spec

- Used a native `<select>` instead of a fully custom searchable combobox. Trade-off: less search UX (browser native filter via type-to-jump only); gain: less JS, RTL-correct out of the box, no JS state to keep in sync with the current FK. With 20 banks the type-to-jump native UX is acceptable.

## Dependencies

- Ticket #507, #508, #509, #510

## Progress Notes

- 2026-04-27: Created — Phase 1 combobox edit ticket
- 2026-04-27: Completed — Edit form gets a `system_bank_id` `<select>` populated with all active Egypt banks; view fetches them with bilingual names resolved for current locale. POST update reads field as explicit (present-but-empty = clear, absent = leave alone). Added autouse session fixture in `conftest.py` to re-seed `system_banks` after `transactional_db` truncates. 13 HTTP tests in `test_system_bank_views.py`. 1815 tests passing.
