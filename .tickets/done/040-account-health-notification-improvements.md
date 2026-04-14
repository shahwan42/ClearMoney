---
id: "040"
title: "Account health notification improvements"
type: improvement
priority: medium
status: done
created: 2026-04-03
updated: 2026-04-15
---

## Description

Improve account health notifications: fix Decimal comparison bug, enrich messages with actual values, add polling interval, show all notifications at once, add severity colors, and add dismiss button.

## Acceptance Criteria

- [x] Fix float comparison in load_health_warnings to use Decimal
- [x] Include actual balance/threshold values in warning messages
- [x] Add 5-minute polling interval in push.js
- [x] Show all unseen notifications (not just first)
- [x] Add dismiss button to push banner and dashboard health warnings
- [x] Use amber for min_monthly_deposit, red for min_balance on dashboard
- [x] All tests pass, lint clean

## Progress Notes

- 2026-04-03: Started — Implementing 6 improvements to account health notifications
- 2026-04-15: Verified — All criteria already implemented. Decimal comparison at accounts/services.py:825, value enrichment at lines 833-840, 5-min polling at push.js:13, all notifications iterated at push.js:103, dismiss buttons in push.js:122-135 and _health_warnings.html:9,16, severity colors (red/amber) in _health_warnings.html:5-19. All 1252 tests pass, lint clean.
