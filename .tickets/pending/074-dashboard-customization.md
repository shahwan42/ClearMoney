---
id: "074"
title: "Dashboard customization"
type: feature
priority: low
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Let users reorder and show/hide dashboard panels. Not everyone uses investments, virtual accounts, or people tracking.

## Acceptance Criteria

- [ ] Settings page section for dashboard layout configuration
- [ ] Toggle visibility of each dashboard panel (net worth, budgets, credit cards, VAs, people, investments, streaks, recent transactions)
- [ ] Drag-to-reorder panels (or up/down arrows for accessibility)
- [ ] Persist layout per user
- [ ] Default layout matches current panel order
- [ ] Dashboard renders only visible panels (skip hidden panel data queries for performance)
- [ ] Service-layer tests for layout save/load, default fallback
- [ ] E2E test for hiding a panel → dashboard no longer shows it

## Technical Notes

- New model: `DashboardLayout` or use JSONB field on User/UserConfig
- Layout format: `[{"panel": "net_worth", "visible": true, "order": 1}, ...]`
- Dashboard view checks layout before calling sub-services (skip hidden panel queries)
- Additive change: default layout = current behavior if no layout configured

## Progress Notes

- 2026-03-31: Created — planned as Tier 3 feature recommendation
