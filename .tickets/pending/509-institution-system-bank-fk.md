---
id: "509"
title: "Institution.system_bank FK + display updates"
type: feature
priority: high
status: pending
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

- [ ] Migration adds `system_bank_id` nullable FK to `institutions` table
- [ ] `on_delete=SET_NULL` — no cascade delete
- [ ] `_institution_icon.html` renders `<img src="{% static svg_path %}">` when system bank SVG present
- [ ] Institution list/detail shows bilingual name from system bank when FK set
- [ ] Existing institutions with `system_bank=null` render identically to before (no regression)
- [ ] Service helper `get_institution_display()` returns correct name for current user language
- [ ] Unit tests: linked institution shows system bank name; unlinked shows own name; SVG renders; emoji fallback
- [ ] `make test && make lint` pass

## Dependencies

- Ticket #507 (SystemBank model)
- Ticket #508 (SVG assets present in static/)

## Progress Notes

- 2026-04-27: Created — Phase 1 FK + display ticket
