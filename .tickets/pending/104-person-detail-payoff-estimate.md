---
id: "104"
title: "Person detail payoff estimate and settle CTA"
type: improvement
priority: low
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Person detail page computes `projected_payoff` and `progress_pct` but doesn't prominently display them. Add "Debt-free in X months" headline and a "Settle Up" CTA button.

## Acceptance Criteria

- [ ] Prominent "Debt-free in X months" card at top of person detail (when debt exists)
- [ ] Progress bar showing repayment progress percentage
- [ ] "Settle Up" button: pre-fills a loan_repayment transaction for remaining balance
- [ ] "Settle Up" links to transaction form with person, amount, and type pre-filled
- [ ] Handles multi-currency: show per-currency payoff estimates
- [ ] Edge cases: no repayments yet → "No repayment history", overpaid → "Settled"
- [ ] E2E test for viewing payoff estimate and clicking Settle Up

## Technical Notes

- `projected_payoff` already computed in `people/services.py:476-490`
- `progress_pct` computed at line 441-466
- Template: `backend/people/templates/people/person_detail.html`
- "Settle Up" link: `/transactions/new?type=loan_repayment&person_id=X&amount=Y`
- Ensure payoff data is included in view context (may need to add to `get_by_id` response)

## Progress Notes

- 2026-03-31: Created — surfaces existing computed data and adds actionable CTA
