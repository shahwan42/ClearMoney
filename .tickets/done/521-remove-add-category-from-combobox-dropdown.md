---
id: "521"
title: "Remove add-category option from combobox dropdown"
type: improvement
priority: medium
status: done
created: 2026-04-28
updated: 2026-04-29
---

## Description

Remove the "+ Add new category" option that appears at the bottom of the category combobox dropdown list. The inline `+` button beside the combobox remains as the entry point for creating new categories.

## Affected User Journeys

- J-2 (Create Expense): category selection in quick entry and transaction forms

## Acceptance Criteria

- [x] Combobox dropdown no longer shows "+ Add new category" at bottom
- [x] Inline `+` button beside combobox still opens new-category bottom sheet
- [x] `category:created` event still auto-selects newly created category in combobox
- [x] J-2 walkthrough passes

## Progress Notes

- 2026-04-28: Started — Removed addBtn block from `CategoryCombobox.prototype._renderOptions` in `static/js/category-combobox.js`
- 2026-04-29: Completed — addBtn block removed; activeCombobox still assigned via focus/click on textInput so category:created auto-select unaffected; 1833 tests pass
