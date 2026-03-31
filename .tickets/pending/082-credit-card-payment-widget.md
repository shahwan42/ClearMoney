---
id: "082"
title: "Credit card payment widget"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

One-tap "Pay CC Bill" button that pre-fills a transfer from a checking/savings account to the credit card for the statement balance. Payment reminders before due date.

## Acceptance Criteria

- [ ] "Pay Bill" button on credit card account detail and dashboard CC section
- [ ] Pre-fills transfer form: source = user's primary checking account, destination = CC, amount = statement balance
- [ ] Statement balance computed from existing billing cycle logic
- [ ] Push notification reminders at 7, 3, and 1 days before due date
- [ ] Mark CC as "paid" after transfer completes
- [ ] Service-layer tests for payment pre-fill logic, reminder scheduling
- [ ] E2E test for clicking Pay Bill → transfer form pre-filled → submit → balance updated

## Technical Notes

- Billing cycle logic exists in `core/billing.py` and `accounts/services.py` (`get_statement_data`)
- Pre-fill uses existing move-money/transfer form with query params
- Reminders: extend `NotificationService.get_pending_notifications()` with due date checks
- No new models — uses existing transfer flow

## Progress Notes

- 2026-03-31: Created — streamlines existing CC payment workflow
