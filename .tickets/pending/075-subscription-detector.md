---
id: "075"
title: "Subscription detector"
type: feature
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Auto-scan transaction history for recurring patterns (same amount, similar note, monthly interval) and suggest creating recurring rules. Helps users discover subscriptions they're not tracking.

## Acceptance Criteria

- [ ] Service method scans last 3-6 months of transactions for recurring patterns
- [ ] Detection criteria: same amount (±5%) + similar note + ~30-day interval + ≥2 occurrences
- [ ] Surface detected subscriptions on recurring rules page: "We noticed these patterns"
- [ ] One-click "Track this" creates a recurring rule from the detected pattern
- [ ] Dismiss option to ignore false positives (persist dismissal)
- [ ] Dashboard callout when new subscriptions are detected
- [ ] Service-layer tests for pattern detection with edge cases (variable amounts, skipped months)
- [ ] E2E test for viewing suggestions and creating a recurring rule from one

## Technical Notes

- Query: group transactions by (note ILIKE, amount ±5%, user_id), filter groups with ≥2 entries ~30 days apart
- Store dismissals in a simple model or JSONB on user config
- Reuse `RecurringService.create()` for the one-click action
- Run detection on recurring rules page load (cached) or as background job

## Progress Notes

- 2026-03-31: Created — leverages existing transaction data for pattern discovery
