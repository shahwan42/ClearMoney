---
id: "061"
title: "Global search"
type: feature
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Add a search bar to the header that searches transactions by note, amount, and category name. HTMX-powered with instant results.

## Acceptance Criteria

- [ ] Search icon in header opens a search input (HTMX partial)
- [ ] Type-ahead with 300ms debounce triggers search via `hx-get`
- [ ] Search matches: transaction note (contains), amount (exact/prefix), category name (contains)
- [ ] Results rendered as transaction list partial (reuse existing transaction row template)
- [ ] Click result navigates to transaction detail bottom sheet
- [ ] Empty query clears results
- [ ] Search scoped to current user (user_id filter)
- [ ] Keyboard accessible: Escape closes, Enter selects first result
- [ ] Service-layer tests for search query logic
- [ ] E2E test for search → results → click result flow

## Technical Notes

- New endpoint: `GET /search?q=...` returning HTML partial
- Add `search()` method to `TransactionService` using `Q` objects with `icontains`
- Consider adding DB index on `note` field if performance is an issue (GIN trigram)
- Reuse `backend/templates/transactions/_transaction_row.html` for result rendering

## Progress Notes

- 2026-03-31: Created — planned as Tier 1 feature recommendation
