---
id: "168"
title: "Account soft-delete (remove without losing history)"
type: feature
priority: high
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Replace hard-delete of accounts with a soft-delete (archive) flow. Removed accounts are hidden from all active views but their transactions remain visible in global transaction history. Balance must be zero before removal.

## Acceptance Criteria

- [ ] `Account` model has `deleted_at DateTimeField(null=True)`
- [ ] `AccountService.remove()` enforces zero balance, archives VAs, deletes recurring rules, sets `deleted_at`
- [ ] Removed accounts excluded from net worth, dropdowns, dashboard, account list
- [ ] Global transaction list shows transactions from removed accounts with "(removed)" label
- [ ] Account detail page returns 404 for removed accounts
- [ ] Institution deletion blocked if active accounts exist
- [ ] UI: "Delete account" button uses new remove endpoint with updated confirm copy
- [ ] Tests: service, view, isolation, balance enforcement

## Progress Notes

- 2026-04-27: Started — implementing migration, service, views, templates
- 2026-04-27: Completed — migration added, AccountService.remove() with zero-balance enforcement, VA archiving, recurring rule cleanup, InstitutionService.delete() blocked by active accounts, transaction row shows "(removed)" label, 13 new tests, 1652 passing
