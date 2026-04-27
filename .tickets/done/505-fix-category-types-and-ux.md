---
id: "505"
title: "Fix category types and new category bottom sheet UX"
type: feature
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Categories are all stored as `type="expense"` even income ones (Salary, Freelance, etc.).
Fix types, filter combobox by tx type, and replace inline add form with bottom sheet.

## Acceptance Criteria

- [x] Income categories (Salary, Freelance, Investment Returns, Refund, Loan Repayment Received) have `type="income"` in DB
- [x] Category combobox shows only expense categories when expense is selected, income when income is selected
- [x] "+" button beside category combobox opens "New Category" bottom sheet
- [x] Bottom sheet pre-fills type from context (expense/income)
- [x] After creating a category via bottom sheet, it auto-selects in the combobox
- [x] Categories settings page has Expenses/Income tabs instead of inline form
- [x] User-created categories can be expense or income

## Progress Notes

- 2026-04-27: Started — implementing data migration, service fix, combobox update, bottom sheet
- 2026-04-27: Completed — all criteria verified visually; 1756 tests pass, lint clean
