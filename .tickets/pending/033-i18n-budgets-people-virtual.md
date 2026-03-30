---
id: "033"
title: "i18n strings — budgets + people + virtual accounts"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Wrap all hardcoded English strings in budgets, people, and virtual accounts templates with Django translation tags. Add Arabic translations.

## Acceptance Criteria

- [ ] `{% load i18n %}` added to all 9 templates (budgets 2, people 4, virtual_accounts 3)
- [ ] ~30 strings extracted: "Budgets", "Total Monthly Budget", "remaining", "Over budget by", budget warnings, "People", loan tracking text, virtual account labels
- [ ] Arabic translations added to `.po` file
- [ ] All pages render correctly in both languages
- [ ] `make test` passes

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/budgets/templates/budgets/` (2 files)
- `backend/people/templates/people/` (4 files)
- `backend/virtual_accounts/templates/virtual_accounts/` (3 files)
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for budgets, people, virtual accounts
