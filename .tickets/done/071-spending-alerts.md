---
id: "071"
title: "Smart spending alerts"
type: feature
priority: medium
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

Proactive notifications when budget thresholds are crossed, unusual spending is detected, or account balances drop below configured minimums.

## Acceptance Criteria

- [ ] Budget threshold alert: "You've spent 80% of your Food budget with 10 days left"
- [ ] Unusual spending alert: "500 EGP expense is 3x your average for this category"
- [ ] Low balance alert: triggers when account drops below `min_balance` health config
- [ ] Daily/weekly spending digest (optional, configurable in settings)
- [ ] Alerts delivered via existing push notification system
- [ ] Service-layer tests for each alert trigger condition
- [ ] E2E test for creating a transaction that triggers an alert → notification appears

## Technical Notes

- Extend `NotificationService` in `push/services.py` with new trigger methods
- Budget threshold: check `percentage >= 80` in `get_pending_notifications()`
- Unusual spending: compare transaction amount vs. category's 30-day average
- Account health alerts already partially exist — extend with push delivery
- Digest: new management command run via cron/background job

## Progress Notes

- 2026-03-31: Created — planned as Tier 3 feature recommendation
