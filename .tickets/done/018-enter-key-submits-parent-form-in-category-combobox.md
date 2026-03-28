---
id: "018"
title: "Enter key in new-category form submits parent form"
type: bug
priority: high
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

When creating a budget and using the inline "+ Add new category" feature in the category combobox, pressing Enter after typing a category name submits the parent budget form instead of saving the new category. This causes a "Category is required" error because the hidden `category_id` input is still empty.

**Root cause:** The `nameInput` and `iconInput` inside `_buildAddForm()` in `category-combobox.js` have no `keydown` handler to intercept Enter. Browser default behavior submits the enclosing `<form>` on Enter keypress.

## Acceptance Criteria

- [x] Pressing Enter in the new-category name input saves the category (does not submit the parent form)
- [x] Pressing Enter in the new-category icon input saves the category (does not submit the parent form)
- [x] Pressing Escape in either input closes the dropdown
- [x] After saving via Enter, the new category is auto-selected in the combobox
- [x] Existing category selection via click still works
- [x] Existing keyboard navigation (ArrowUp/Down, Enter to select, Escape to close) still works
- [x] No lint or test regressions

## Progress Notes

- 2026-03-28: Started — identified root cause: Enter in add-form inputs triggers parent form submit
- 2026-03-28: Fix applied — added keydown handler for Enter/Escape on nameInput and iconInput in _buildAddForm()
- 2026-03-28: All AC verified — 1185 unit tests pass, 154 E2E tests pass, lint clean. Code review confirms all paths handled correctly.
- 2026-03-28: Completed — fix committed, ticket closed.
