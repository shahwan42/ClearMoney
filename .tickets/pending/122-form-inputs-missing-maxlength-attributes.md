---
id: "122"
title: "Form inputs missing maxlength attributes across multiple pages"
type: bug
priority: low
status: pending
created: 2026-04-17
updated: 2026-04-17
---

## Description

Multiple text inputs across the app are missing `maxlength` attributes, violating the QA Guidelines (Section 6) which require all text inputs to align with DB model `max_length` constraints.

## Affected Inputs

| Page | Form | Input | Missing Attribute |
|------|------|-------|-------------------|
| Dashboard / Quick Entry | `#quick-entry-form` | `tags` (comma-separated) | `maxlength` |
| Dashboard / Quick Entry | `#quick-entry-form` | category search (unnamed text input) | `maxlength` |
| Dashboard / Move Money | `#move-money-form` | `note` | `maxlength` |
| Settings / Tags | Tag creation form | `name` | `maxlength` |

## Verified Via

```js
// Quick entry form inspection
document.getElementById('quick-entry-form')
  .querySelectorAll('input[type="text"]')
  // tags: maxlength=null, category search: maxlength=null, note: maxlength=500 (OK)
  
// Move money form
document.getElementById('move-money-form')
  .querySelector('input[name="note"]').maxLength  // -1 (unset)
  
// Tags settings
document.querySelector('input[name="name"]').maxLength  // -1 (unset)
```

## Acceptance Criteria

- [ ] All `input[type="text"]` elements have `maxlength` matching the corresponding model field `max_length`
- [ ] `tags` input in Quick Entry: `maxlength` set to reasonable value (e.g. 500 for the whole comma-separated string, or document expected format)
- [ ] Category search combobox: `maxlength` set (e.g. 100)
- [ ] Move Money `note`: `maxlength="500"` (match Transaction note)
- [ ] Tag name input on `/settings/tags`: `maxlength` set to match `Tag.name` model field

## Progress Notes

- 2026-04-17: Filed during manual QA session (ticket #117). Verified via browser JS form inspection.
