---
id: "088"
title: "Installment tracker"
type: feature
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Track "buy now pay later" installment purchases: total amount, monthly payment, remaining installments, total interest paid. Common in Egyptian market (Valū, Souhoola, Contact).

## Acceptance Criteria

- [ ] New model: `Installment` (user_id, merchant, total_amount, monthly_payment, total_installments, paid_installments, interest_rate, start_date, account_id)
- [ ] Create installment plan from settings or dedicated page
- [ ] Dashboard widget: total monthly installment obligations
- [ ] Detail view: payment schedule with paid/remaining breakdown
- [ ] Link installment payments to transactions (mark as installment payment)
- [ ] Alert when installment payment is due
- [ ] Service-layer tests for installment creation, payment tracking, completion
- [ ] E2E test for creating installment → making payment → progress updated

## Technical Notes

- Monthly payment could auto-create recurring rules
- Or track independently and match against transactions
- Interest calculation: `total_paid - original_amount = total_interest`
- Completion: when `paid_installments >= total_installments`, mark as done
- Push notification for upcoming installment due dates

## Progress Notes

- 2026-03-31: Created — addresses common Egyptian fintech payment pattern
