---
id: "086"
title: "Weekly email digest"
type: feature
priority: low
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Send a weekly email summary with top spending categories, budget status, net worth change, and unusual spending. Drives engagement for users who don't open the app daily.

## Acceptance Criteria

- [ ] Weekly email sent every Monday morning with previous week's summary
- [ ] Content: total spent, top 3 categories, budget status (on track / over), net worth change
- [ ] Unusual spending callout if any category > 150% of weekly average
- [ ] Opt-in toggle in settings (default: off)
- [ ] Unsubscribe link in email
- [ ] HTML email template (responsive, dark-mode compatible)
- [ ] Background job: new management command `send_weekly_digest`
- [ ] Service-layer tests for digest data assembly
- [ ] E2E test for enabling digest in settings

## Technical Notes

- Aggregate from `DailySnapshot` data (daily_spending, daily_income, net_worth_egp)
- Reuse existing `EmailService` for sending via Resend
- New management command scheduled via cron or startup job
- Opt-in flag: new field on User model or UserConfig

## Progress Notes

- 2026-03-31: Created — leverages existing snapshot data and email infrastructure
