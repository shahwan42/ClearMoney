---
id: "087"
title: "Account grouping / portfolios"
type: feature
priority: low
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Let users group accounts into custom portfolios (e.g., "Emergency Fund", "Daily Use") and track group totals on the dashboard.

## Acceptance Criteria

- [ ] Create named account groups in settings
- [ ] Assign accounts to groups (one account can belong to multiple groups)
- [ ] Dashboard shows group totals as summary cards
- [ ] Group detail page lists member accounts with individual balances
- [ ] Reorder and rename groups
- [ ] Default group: "All Accounts" (implicit, always exists)
- [ ] Service-layer tests for group CRUD and total calculation
- [ ] E2E test for creating group → assigning accounts → viewing total

## Technical Notes

- New model: `AccountGroup` (user_id, name, display_order) + M2M with Account
- Or leverage existing `role_tags` ArrayField on Account (simpler but less flexible)
- Group total = Sum of member account current_balance
- Add to dashboard as collapsible sections or summary cards

## Progress Notes

- 2026-03-31: Created — provides flexible account organization beyond institutions
