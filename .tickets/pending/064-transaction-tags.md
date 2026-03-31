---
id: "064"
title: "Transaction tags"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Add a tagging system for transactions. Tags allow cross-cutting analysis beyond single-select categories (e.g., "vacation", "wedding", "tax-deductible").

## Acceptance Criteria

- [ ] New `Tag` model with many-to-many relationship to Transaction
- [ ] Tag input on transaction create/edit forms (comma-separated, auto-suggest existing tags)
- [ ] Tag filter on transaction list page
- [ ] Report: spending by tag across all categories
- [ ] Tag management in settings (rename, merge, delete)
- [ ] Tags displayed on transaction rows and detail view
- [ ] Service-layer tests for tag CRUD, filtering, reporting
- [ ] E2E test for adding tags → filtering by tag → viewing tag report

## Technical Notes

- Transaction model already has an ArrayField `tags` — evaluate whether to use that or a proper M2M with a Tag model
- If using existing ArrayField: simpler, but no referential integrity or rename support
- If new Tag model: better for management UI, reporting, and auto-suggest
- Recommend new Tag model for proper normalization

## Progress Notes

- 2026-03-31: Created — planned as Tier 1 feature recommendation
