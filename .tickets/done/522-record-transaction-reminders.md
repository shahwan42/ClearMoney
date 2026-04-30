---
id: "522"
title: "Record transaction reminders — twice-daily smart nudge"
type: feature
priority: medium
status: done
created: 2026-04-30
updated: 2026-04-30
---

## Description

Add smart twice-daily reminders to the notification center prompting users to log their transactions. No user configuration required. Reminders fire based on whether any transaction has been recorded in each time window.

## Affected User Journeys

- J-2 (Financial Loop): indirectly improves data completeness by nudging recording. No behavioral change to the recording flow itself.
- None of CP-1..CP-6 critical paths are modified — purely additive to NotificationService.

## Acceptance Criteria

- [x] Morning reminder (8am+): fires if no transaction recorded since yesterday 9pm
- [x] Evening reminder (9pm+): fires if no transaction recorded since today 8am
- [x] All 7 transaction types suppress the reminder (transfer type tested explicitly)
- [x] Tag format: `record-reminder-morning-YYYY-MM-DD` / `record-reminder-evening-YYYY-MM-DD`
- [x] Auto-resolves when user records a transaction (existing `generate_and_persist` behavior)
- [x] Notification center only (no browser push banner)
- [x] Zero user configuration
- [x] 11 tests passing, no regressions (79 push tests total green)

## Progress Notes

- 2026-04-30: Started — designing via grill-me. Hybrid C approach: morning=check since yesterday 9pm, evening=check since today 8am. Pure service addition, no migrations.
- 2026-04-30: Completed — Added `_get_record_reminders()` to `NotificationService` in `push/services.py`. 11 new tests in `TestRecordReminders`. No migrations, no new URLs, no templates. Deployed via existing hourly cron.
