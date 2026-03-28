---
id: "011"
title: "Merge transfer & exchange into Move Money tab"
type: feature
priority: medium
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

Merge the separate Transfer and Exchange tabs in the quick-entry bottom sheet into a single "Move Money" tab. The form auto-detects transfer mode (same currency) vs exchange mode (different currencies) based on selected accounts. Reduces 3 tabs to 2 (Transaction + Move Money).

## Acceptance Criteria

- [x] Single "Move Money" tab replaces Exchange + Transfer tabs in bottom sheet
- [x] Auto-detects transfer vs exchange mode from account currencies
- [x] Transfer fields (fee) shown for same-currency accounts
- [x] Exchange fields (rate, counter amount) shown for different-currency accounts
- [x] Existing POST endpoints unchanged (/transactions/transfer, /transactions/exchange-submit)
- [x] Old URLs (/transfers/new, /exchange/new) redirect to /move-money/new
- [x] All unit tests pass (1184 passed)
- [x] All E2E tests pass (154 passed)
- [x] Full page /move-money/new works

## Progress Notes

- 2026-03-28: Started — Creating unified template and JS, updating nav and views
- 2026-03-28: Completed — Unified form, mode detection JS, 2-tab nav, old URLs redirect, 1164 tests passing
