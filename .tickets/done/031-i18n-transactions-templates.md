---
id: "031"
title: "i18n strings — transactions templates"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Wrap all hardcoded English strings in transaction templates with Django translation tags. Add Arabic translations. This is the largest app by template count.

## Acceptance Criteria

- [ ] `{% load i18n %}` added to all 22 transaction templates
- [ ] ~60 strings extracted: "Transactions", "Search notes...", "All Accounts", "Expense", "Income", form labels, tips, swipe instructions, success/error messages
- [ ] Arabic translations added to `.po` file
- [ ] Transaction list, forms, transfer, exchange, batch entry render correctly in both languages
- [ ] `make test` and `make test-e2e` pass

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/transactions/templates/transactions/` (all 22 files)
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for transaction templates (largest app)
