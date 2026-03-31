---
id: "089"
title: "Streak gamification and milestones"
type: feature
priority: low
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Enhance the existing streak tracking with milestone badges, achievements, and motivational notifications. Currently streak is just a number on the dashboard.

## Acceptance Criteria

- [ ] Milestone badges: 7-day, 14-day, 30-day, 60-day, 90-day, 365-day streaks
- [ ] Transaction count milestones: 50, 100, 250, 500, 1000 transactions
- [ ] Visual badge/icon on dashboard when milestone reached
- [ ] Push notification: "Congratulations! 30-day streak!"
- [ ] "Don't break your streak" reminder if no transaction logged by evening
- [ ] Milestone history: view all earned badges in settings or profile
- [ ] Service-layer tests for milestone detection logic
- [ ] E2E test for reaching milestone → badge appears on dashboard

## Technical Notes

- Streak already computed in `transactions/services/activity.py` (`load_streak()`)
- New model: `UserMilestone` (user_id, milestone_type, achieved_at) or store in JSONB
- Check milestones during streak calculation — if new milestone crossed, trigger notification
- Push notification: extend `NotificationService.get_pending_notifications()`
- Badges: simple SVG/emoji icons in template

## Progress Notes

- 2026-03-31: Created — gamifies existing streak tracking for engagement
