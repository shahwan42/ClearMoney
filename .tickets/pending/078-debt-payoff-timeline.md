---
id: "078"
title: "Debt payoff timeline visualizer"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Surface the already-computed `projected_payoff` data from people/services.py as prominent visual timeline cards showing when each debt will be fully repaid.

## Acceptance Criteria

- [ ] People page: prominent "Debt-free from [Person] in X months" cards
- [ ] Visual progress bar showing repayment progress per person
- [ ] Timeline view: estimated payoff dates for all active debts
- [ ] "Fastest to repay" and "largest debt" highlights
- [ ] Dashboard summary: "You'll be fully debt-free by [date]"
- [ ] Service-layer tests for timeline calculation edge cases (no repayments yet, overpaid)
- [ ] E2E test for viewing debt timeline with active loans

## Technical Notes

- `projected_payoff` already computed in `people/services.py` (line 476-490) based on repayment velocity
- `progress_pct` also computed (line 441-466) — use for progress bars
- Mostly template/UI work — data computation already exists
- Add timeline section to people list page and dashboard people summary

## Progress Notes

- 2026-03-31: Created — surfaces existing computed data that's currently buried
