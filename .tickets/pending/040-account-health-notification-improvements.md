---
id: "040"
title: "Account health notification improvements"
type: improvement
priority: medium
status: wip
created: 2026-04-03
updated: 2026-04-03
---

## Description

Improve account health notifications: fix Decimal comparison bug, enrich messages with actual values, add polling interval, show all notifications at once, add severity colors, and add dismiss button.

## Acceptance Criteria

- [ ] Fix float comparison in load_health_warnings to use Decimal
- [ ] Include actual balance/threshold values in warning messages
- [ ] Add 5-minute polling interval in push.js
- [ ] Show all unseen notifications (not just first)
- [ ] Add dismiss button to push banner and dashboard health warnings
- [ ] Use amber for min_monthly_deposit, red for min_balance on dashboard
- [ ] All tests pass, lint clean

## Progress Notes

- 2026-04-03: Started — Implementing 6 improvements to account health notifications
