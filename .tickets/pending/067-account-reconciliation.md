---
id: "067"
title: "Account reconciliation"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Add a reconciliation workflow so users can verify ClearMoney balances match their real bank balances.

## Acceptance Criteria

- [ ] "Reconcile" button on account detail page
- [ ] User enters real bank balance → system shows difference
- [ ] List of recent unverified transactions shown for review
- [ ] Mark individual transactions as "verified" during reconciliation
- [ ] New field on Transaction: `is_verified` (Boolean, default False)
- [ ] New field on Account: `last_reconciled_at` (DateTimeField, nullable)
- [ ] Dashboard warning for accounts not reconciled in 30+ days
- [ ] Service-layer tests for reconciliation flow, balance comparison
- [ ] E2E test for reconcile → enter balance → mark transactions → complete

## Technical Notes

- Additive migration: `is_verified` on Transaction, `last_reconciled_at` on Account
- Reconciliation is a read-heavy operation — show transactions since last reconciliation
- Balance difference = entered_balance - current_balance (positive = missing income, negative = missing expense)
- Do not auto-adjust balance — user must find and fix discrepancies manually

## Progress Notes

- 2026-03-31: Created — planned as Tier 2 feature recommendation
