---
id: "032"
title: "i18n strings — accounts templates"
type: feature
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-15
---

## Description

Wrap all hardcoded English strings in account templates with Django translation tags. Add Arabic translations.

## Acceptance Criteria

- [ ] `{% load i18n %}` added to all 13 account templates
- [ ] ~35 strings extracted: "Accounts", "+ Account", "No accounts yet", form labels (Type, Currency, Custom name, Initial Balance, Credit Limit), institution card text
- [ ] Arabic translations added to `.po` file
- [ ] Account list, forms, institution cards render correctly in both languages
- [ ] `make test` passes

## Dependencies

- Ticket #022 (i18n infrastructure)

## Files

- `backend/accounts/templates/accounts/` (all 13 files)
- `backend/locale/ar/LC_MESSAGES/django.po`

## Progress Notes

- 2026-03-30: Created — i18n for account templates
- 2026-04-14: Completed — All 13 account templates have {% load i18n %} and {% trans %} tags. Arabic translations added. All 1252 tests pass.
