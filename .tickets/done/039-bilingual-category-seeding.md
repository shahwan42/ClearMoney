---
id: "039-done"
title: "Bilingual category seeding [DONE]"
status: done
created: 2026-03-30
updated: 2026-03-30
---

## Description

Update the default category seeding to store both English and Arabic names in the JSONB `name` field. All 27 default categories get Arabic translations.

## Acceptance Criteria

- [ ] `_seed_default_categories()` in `auth_app/services.py` updated to store JSONB: `{"en": "Food & Groceries", "ar": "طعام وبقالة"}`
- [ ] All 27 default categories have Arabic translations:
  - Household → منزل, Food & Groceries → طعام وبقالة, Transport → مواصلات, Health → صحة, Education → تعليم
  - Mobile → موبايل, Electricity → كهرباء, Gas → غاز, Internet → إنترنت, Gifts → هدايا
  - Entertainment → ترفيه, Shopping → تسوق, Subscriptions → اشتراكات, Insurance → تأمين
  - Fees & Charges → رسوم ومصاريف, Debt Payment → سداد ديون, Salary → راتب, Freelance → عمل حر
  - Investment Returns → عوائد استثمار, Refund → استرداد, Loan Repayment Received → سداد قرض
  - Other → أخرى, Travel → سفر, Cafe → كافيه, Restaurant → مطعم, Car → سيارة
  - Virtual Fund → صندوق افتراضي
- [ ] New user registration seeds categories with both language names
- [ ] `make test` passes

## Dependencies

- Ticket #038 (JSONB migration)

## Files

- `backend/auth_app/services.py`

## Progress Notes

- 2026-03-30: Created — Arabic translations for default categories
