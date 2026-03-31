---
id: "084"
title: "Transaction templates / favorites"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Save frequently-used transactions as templates for one-tap entry. Different from recurring — these are on-demand (e.g., "Morning coffee - 45 EGP - Food").

## Acceptance Criteria

- [ ] New model: `TransactionTemplate` (user_id, name, amount, category_id, account_id, note, type)
- [ ] "Save as template" option on transaction detail
- [ ] "Favorites" section on quick-entry bottom sheet showing saved templates
- [ ] One-tap creates transaction from template with today's date
- [ ] Edit and delete templates in settings
- [ ] Max 20 templates per user
- [ ] Service-layer tests for template CRUD and transaction creation
- [ ] E2E test for saving template → using it → transaction created

## Technical Notes

- Similar structure to `RecurringRule.template_transaction` JSONB — could use same format
- Or new model for better querying and management
- Quick-entry sheet already exists — add templates section above the form
- Template creates transaction via existing `TransactionService.create()`

## Progress Notes

- 2026-03-31: Created — reduces friction for repetitive manual transactions
