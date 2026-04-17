---
id: "124"
title: "UX: Reconciliation warning banners shown for brand-new accounts with no transaction history"
type: improvement
priority: low
status: done
created: 2026-04-17
updated: 2026-04-17
---

## Description

The dashboard shows a **"[Account] has never been reconciled"** warning banner for every account, including accounts that were just created moments ago with no transactions. This is noisy and confusing for new users who haven't had a chance to reconcile anything yet.

**Observed:** 4 yellow warning banners stacked at the top of the dashboard immediately after account creation  
**Expected:** Warning only shown after the account has had at least one transaction, or after a configurable grace period (e.g. 30 days)

## Screenshot

See: `.tickets/attachments/qa-02-dashboard-with-data.png` — 4 banners visible on first data load.

## Suggested Fix

In the banner-render logic, add a condition:
- Only show the reconciliation warning if the account has at least one transaction AND has never been reconciled, OR
- Only show if the account is older than 30 days and has never been reconciled

## Acceptance Criteria

- [x] New accounts (0 transactions, or created < 30 days ago) do not show the "never been reconciled" banner
- [x] Existing accounts with transaction history continue to show the banner as before
- [x] The banners are still dismissible (×) as currently implemented

## Progress Notes

- 2026-04-17: Filed during manual QA session (ticket #117). UX issue noted on first load of fresh test account.
- 2026-04-17: Implemented fix in `load_health_warnings`. Added transaction check and 30-day grace period. Updated and added tests.
