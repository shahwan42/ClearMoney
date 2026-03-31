---
id: "081"
title: "Auto-categorization rules"
type: feature
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Let users define pattern-based rules that auto-assign categories to transactions. "When note contains 'Uber', categorize as Transport."

## Acceptance Criteria

- [ ] New model: `CategoryRule` (user_id, pattern, match_type, category_id, priority)
- [ ] Match types: "contains", "starts with", "exact match" (case-insensitive)
- [ ] Rules applied automatically during `TransactionService.create()` when no category provided
- [ ] Settings page for managing rules: create, edit, delete, reorder priority
- [ ] "Create rule from this transaction" shortcut on transaction detail
- [ ] Rules don't override manually-set categories
- [ ] Service-layer tests for pattern matching, priority ordering, edge cases
- [ ] E2E test for creating rule → adding transaction → auto-categorized

## Technical Notes

- New model in `core/models.py` with `UserScopedManager`
- Apply in `TransactionService.create()` before `suggest_category()` fallback
- Priority field determines which rule wins on multiple matches
- Migration: additive only (new table)
- Could also retroactively apply rules to existing uncategorized transactions

## Progress Notes

- 2026-03-31: Created — eliminates repetitive manual categorization
