---
id: "511"
title: "Institution edit — system bank combobox"
type: feature
priority: high
status: pending
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

- [ ] Edit form shows combobox pre-populated when institution has `system_bank`
- [ ] Edit form shows empty combobox (custom name) when `system_bank` is null
- [ ] Selecting new system bank updates FK + reflects in institution display immediately
- [ ] Clearing system bank reverts institution to custom name (editable)
- [ ] Institution service `update()` handles `system_bank_id` param (set/clear)
- [ ] RTL layout correct in Arabic mode
- [ ] Unit tests: update with system_bank_id set; update clearing system_bank_id
- [ ] E2E test: edit institution → link to system bank → verify display name changes
- [ ] `make test && make test-e2e && make lint` pass

## Dependencies

- Ticket #507, #508, #509, #510

## Progress Notes

- 2026-04-27: Created — Phase 1 combobox edit ticket
