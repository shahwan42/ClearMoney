---
id: "513"
title: "Category create/edit form — dual-language name fields"
type: feature
priority: medium
status: pending
created: 2026-04-27
updated: 2026-04-27
---

## Description

The category create and edit forms currently have a single name input. Since `Category.name` is already JSONB `{"en": ..., "ar": ...}`, the forms need to expose both language fields. The user's current language field is required; the other language is optional (auto-fills with same value if blank).

## UX

Create/edit form shows:
```
Name (English) [required if user is English]  ← pre-filled in English mode
Name (Arabic)  [optional]

OR

الاسم (عربي)    [required if user is Arabic]  ← pre-filled in Arabic mode
الاسم (إنجليزي) [optional]
```

Logic:
- Current language field: `required`
- Other language field: optional; if left blank, service saves same value for both
- Existing categories created with single-language names: edit form pre-fills both fields from existing data (en/ar keys); missing key shown as blank

## Service Changes

`CategoryService.create(name_en, name_ar)` and `update(name_en, name_ar)`:
- Validate at least one of `name_en`/`name_ar` is non-empty
- If one is blank, copy from the other: `name_ar = name_ar or name_en`
- Save as `{"en": name_en, "ar": name_ar}`

## Template Changes

- `settings_app/templates/settings_app/_category_new_form.html` — add `name_ar` input
- Category edit form (if separate) — same change
- Labels localized via `{% trans %}`
- Both inputs: `maxlength="100"` (align with DB field behaviour)

## Acceptance Criteria

- [ ] Create form has both `name_en` and `name_ar` inputs
- [ ] Current-language input is `required`; other is optional
- [ ] Saving with only one language populated auto-fills the other from provided value
- [ ] Edit form pre-populates both fields from existing `name` JSONB
- [ ] Category displays correct language name in both EN and AR modes after save
- [ ] Service validates at least one name is non-empty (raises `ValueError` if both blank)
- [ ] Unit tests: create with both names; create with only en; create with only ar; blank both → error
- [ ] `make test && make lint` pass

## Dependencies

- None (standalone Phase 3 ticket; categories are already JSONB)

## Progress Notes

- 2026-04-27: Created — Phase 3 category form bilingual ticket
