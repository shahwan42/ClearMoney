---
id: "508"
title: "Egypt bank seed data + SVG assets"
type: feature
priority: high
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Populate the `system_banks` table with ~20 Egyptian banks. For each bank: source official SVG logo if available; otherwise create a clean branded SVG with the bank's short name on a brand-colored background. Store SVGs in `static/banks/`.

## Target Bank List (Egypt)

Priority order (by market prevalence):

| # | Short Name | English Name | Arabic Name | Brand Color |
|---|------------|-------------|-------------|-------------|
| 1 | CIB | Commercial International Bank | البنك التجاري الدولي | #003366 |
| 2 | NBE | National Bank of Egypt | البنك الأهلي المصري | #1a4d2e |
| 3 | Banque Misr | Banque Misr | بنك مصر | #8b0000 |
| 4 | QNB | QNB Alahli | بنك قطر الوطني الأهلي | #5c0057 |
| 5 | HSBC | HSBC Egypt | بنك HSBC مصر | #db0011 |
| 6 | SCB | Standard Chartered Egypt | ستاندرد تشارترد مصر | #0072aa |
| 7 | Faisal | Faisal Islamic Bank | بنك فيصل الإسلامي | #006600 |
| 8 | ABK | Al Ahli Bank of Kuwait | البنك الأهلي الكويتي | #003580 |
| 9 | Mashreq | Mashreq Bank Egypt | بنك المشرق مصر | #e60028 |
| 10 | AAIB | Arab African International Bank | البنك العربي الأفريقي الدولي | #004b87 |
| 11 | EGB | Egyptian Gulf Bank | بنك الخليج المصري | #006b9e |
| 12 | Suez Canal | Suez Canal Bank | بنك قناة السويس | #00457c |
| 13 | Blom | Blom Bank Egypt | بنك بلوم مصر | #c8102e |
| 14 | Crédit Agricole | Crédit Agricole Egypt | كريدي أجريكول مصر | #008000 |
| 15 | ADIB | Abu Dhabi Islamic Bank Egypt | بنك أبوظبي الإسلامي مصر | #8b6914 |
| 16 | Arab Bank | Arab Bank Egypt | البنك العربي مصر | #004f9f |
| 17 | Union | Union National Bank Egypt | البنك الوطني المتحد مصر | #003087 |
| 18 | Attijariwafa | Attijariwafa Bank Egypt | بنك التجاري وفا مصر | #e2001a |
| 19 | InstaPay | InstaPay | إنستاباي | #6c0091 |
| 20 | Vodafone Cash | Vodafone Cash | فودافون كاش | #e60000 |

Last two are fintechs/wallets (`bank_type = "fintech"` / `"wallet"`).

## SVG Strategy

For each bank:
1. **First**: search for official SVG logo (Wikipedia, brand asset sites)
2. **Fallback**: generate clean SVG — rounded rect with `brand_color`, white `short_name` text centered, 40×40 viewBox

Fallback SVG template:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
  <rect width="40" height="40" rx="8" fill="{brand_color}"/>
  <text x="20" y="24" text-anchor="middle" fill="white" font-size="10" font-family="system-ui" font-weight="bold">{short_name}</text>
</svg>
```

## Acceptance Criteria

- [ ] Data migration creates all 20 `SystemBank` records with correct bilingual names
- [ ] All 20 SVG files present in `static/banks/` (official or fallback)
- [ ] `svg_path` field populated for all banks (e.g., `"banks/cib.svg"`)
- [ ] `display_order` set so banks appear in priority order above
- [ ] Data migration is idempotent (safe to run twice)
- [ ] `make test && make lint` pass

## Dependencies

- Ticket #507 (SystemBank model must exist)

## Affected User Journeys

- None — internal seed migration. Surfaces only when #509+ link Institutions to SystemBanks.

## Progress Notes

- 2026-04-27: Created — Phase 1 bank data ticket
- 2026-04-27: Completed — Data migration `accounts/0011_seed_egypt_system_banks.py` seeds all 20 banks with bilingual names. Reused 16 existing logos in `static/img/institutions/` (deviation from ticket's `static/banks/` path; matches existing convention). Generated 4 fallback SVGs for Standard Chartered, Blom, InstaPay, Union. Idempotent via `update_or_create((country, short_name))`. 7 unit tests cover count, ordering, bilingual names, SVG presence, types, idempotency, Arabic content.
