---
id: "510"
title: "Institution create — system bank combobox"
type: feature
priority: high
status: done
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

- [x] `GET /api/system-banks` endpoint exists, requires auth, returns active Egypt banks in order; supports `?q=` and `?country=`
- [x] Combobox in `_institution_form.html` includes system banks (with bilingual names + SVG logos) prepended to existing static presets
- [x] Selecting system bank sets hidden `system_bank_id` field
- [x] Typing custom name (no match) saves institution with `system_bank=null`
- [x] System bank selection saves institution with `system_bank` FK set (verified via HTTP test)
- [x] `InstitutionService.create()` handles `system_bank_id` param (added in #509)
- [x] RTL layout: existing combobox is already RTL-aware (uses `start-0 end-0`); no changes needed
- [~] E2E test: SKIPPED — the standalone institution form (`/accounts/institution-form`) is not currently reachable from the user-facing UI (the visible "+ Account" button opens the unified add-account form at `/accounts/add-form`, which uses a separate `presets_json`). HTTP-level coverage at `accounts/tests/test_system_bank_views.py` (9 tests) covers form embed + POST flow + API endpoint + auth + filter + bilingual data. Retrofitting the unified form is deferred — separate scope.
- [x] `make test && make lint` pass — 1811 tests, ruff + mypy clean

## Affected User Journeys

- J-3 (Account Management): institution create flow now offers SystemBank options.
- CP-2 (Core Financial Loop): account creation unchanged (uses unified form, not modified).

## Dependencies

- Ticket #507, #508, #509

## Progress Notes

- 2026-04-27: Created — Phase 1 combobox create ticket
- 2026-04-27: Completed — `/api/system-banks` JSON endpoint, system banks prepended to embedded presets in `_institution_form.html`, hidden `system_bank_id` input, JS preserves FK link on preset select / clears on type-custom or type-change. POST `/institutions/add` reads `system_bank_id`. 9 HTTP tests; E2E skipped due to form not being on user-facing path.
