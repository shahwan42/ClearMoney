---
id: "510"
title: "Institution create — system bank combobox"
type: feature
priority: high
status: pending
created: 2026-04-27
updated: 2026-04-27
---

## Description

Replace the plain text institution name input on the institution creation form with a searchable combobox. The combobox shows all active system banks (Egypt list) ordered by `display_order`. User can also type a custom name that doesn't match any system bank — in which case `system_bank` FK remains null and the typed name is saved as-is.

UX: same combobox pattern already used in the category picker (`static/js/category-combobox.js`).

## UX Flow

1. User opens "Add Institution" form
2. Combobox shows: search field + scrollable list of system banks (SVG logo + bilingual name)
3. Typing filters the list
4. Selecting a system bank: sets hidden `system_bank_id` input, pre-fills name field (read-only), pre-fills type field from system bank's `bank_type`
5. Typing a name not in the list: `system_bank_id` remains empty, name is free text (existing behavior)
6. SVG logo previews next to each option in the dropdown

## API Endpoint

Add `GET /api/system-banks?q=&country=EG` JSON endpoint:

```json
[
  {
    "id": 1,
    "name": "CIB",          // current language
    "short_name": "CIB",
    "svg_path": "banks/cib.svg",
    "brand_color": "#003366",
    "bank_type": "bank"
  },
  ...
]
```

Endpoint is authenticated (no public leak), returns only `is_active=True` banks.

## Form Changes

```html
<!-- Hidden field set by JS when system bank selected -->
<input type="hidden" name="system_bank_id" id="system-bank-id">

<!-- Combobox replaces plain text name input -->
<div id="bank-combobox" ...>...</div>
```

Institution service `create()` updated to accept `system_bank_id` param.

## Acceptance Criteria

- [ ] `GET /api/system-banks` endpoint exists, requires auth, returns active Egypt banks in order
- [ ] Combobox renders in institution create form with SVG logos + bilingual names
- [ ] Selecting system bank sets hidden `system_bank_id`, auto-fills type
- [ ] Typing custom name (no match) saves institution with `system_bank=null`
- [ ] System bank selection saves institution with `system_bank` FK set
- [ ] Institution service `create()` handles `system_bank_id` param
- [ ] RTL layout works correctly in Arabic mode
- [ ] E2E test: create institution via combobox → system bank linked; create custom → no FK
- [ ] `make test && make test-e2e && make lint` pass

## Dependencies

- Ticket #507, #508, #509

## Progress Notes

- 2026-04-27: Created — Phase 1 combobox create ticket
