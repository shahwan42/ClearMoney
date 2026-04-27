---
id: "509"
title: "Institution.system_bank FK + display updates"
type: feature
priority: high
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Add a nullable FK `system_bank` to the `institutions` table. When set, the institution derives its display name (bilingual) and icon from the system bank record. Existing institutions are unaffected (FK is null → current name/icon fields used as before).

Also update the institution display component (`_institution_icon.html` and institution list views) to use `system_bank.svg_path` when available, falling back to the existing emoji/icon field.

## Schema Change

```python
# In core/models.py, on Institution model:
system_bank = models.ForeignKey(
    "SystemBank",
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="institutions",
)
```

`on_delete=SET_NULL` ensures deleting a system bank doesn't cascade to user institutions.

## Display Logic

In `_institution_icon.html` and institution service layer:

```python
def get_display_name(institution, lang=None):
    if institution.system_bank_id:
        return institution.system_bank.get_display_name(lang)
    return institution.name  # existing plain text

def get_icon(institution):
    if institution.system_bank_id and institution.system_bank.svg_path:
        return {"type": "svg", "path": institution.system_bank.svg_path}
    return {"type": "emoji", "value": institution.icon or "🏦"}
```

## Acceptance Criteria

- [x] Migration `0012_institution_system_bank` adds nullable FK to `institutions` table
- [x] `on_delete=SET_NULL` — verified via test (deleting system bank leaves institution with null FK)
- [x] `_institution_icon.html` renders SVG via existing `is_image_icon` filter — service strips `img/institutions/` prefix from `svg_path` and stores basename in `icon` field, so existing template path works transparently
- [x] Institution list/detail shows bilingual name from system bank when FK set (via service `_row_to_dict` overriding name field)
- [x] Existing institutions with `system_bank=null` render identically to before — covered by `test_unlinked_institution_uses_own_fields`
- [x] Service helper resolves correct name for current language via `SystemBank.get_display_name()`
- [x] Unit tests: 11 cases — linked, unlinked, invalid id, name resolution, icon resolution, color resolution, update link/unlink/preserve, SET_NULL cascade
- [x] `make test && make lint` pass — 1802 tests, ruff clean, mypy clean

## Affected User Journeys

- J-3 (Account Management): institution display name/icon resolves via `system_bank` when linked. Unlinked path unchanged.
- CP-2 (Core Financial Loop): institution-creation accepts optional `system_bank_id`; null path unchanged.

## Dependencies

- Ticket #507 (SystemBank model)
- Ticket #508 (SVG assets present in static/)

## Progress Notes

- 2026-04-27: Created — Phase 1 FK + display ticket
- 2026-04-27: Completed — Migration adds nullable FK, service-layer dict-resolution overrides display fields when linked, 11 unit tests, 1802 total tests passing.
