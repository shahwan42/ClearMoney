---
id: "062"
title: "Savings goals with auto-allocation"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Extend virtual accounts with automation: users set a monthly savings target and the system auto-allocates when recurring income arrives.

## Acceptance Criteria

- [ ] New fields on VirtualAccount: `monthly_target` (Decimal, nullable), `auto_allocate` (Boolean, default False)
- [ ] When a recurring rule is confirmed and `auto_allocate` is enabled, allocate to linked virtual account
- [ ] Progress timeline on VA detail: projected completion date based on monthly target
- [ ] Dashboard widget highlights closest-to-goal virtual accounts
- [ ] Settings on VA create/edit form for monthly target and auto-allocate toggle
- [ ] Service-layer tests for auto-allocation logic
- [ ] E2E test for enabling auto-allocate → confirming recurring → VA balance updated

## Technical Notes

- Additive migration only (new nullable fields)
- Auto-allocation triggers in `RecurringService.confirm()` — check for linked VAs
- Projection: `(target - current_balance) / monthly_target` months remaining
- Reuse existing `VirtualAccountService.allocate()` for the actual allocation

## Progress Notes

- 2026-03-31: Created — planned as Tier 1 feature recommendation
