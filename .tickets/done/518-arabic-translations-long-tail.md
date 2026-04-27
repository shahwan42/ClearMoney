---
id: "518"
title: "Arabic translations long-tail + Playwright smoke test"
type: improvement
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Follow-up to #514. The first pass filled 126 of 534 `msgstr ""` entries — high-traffic CP-2/3/4 strings. This ticket fills the remaining ~373 long-tail strings and adds the Playwright smoke test from #514's original acceptance criteria.

## Remaining gaps (by app, after first pass)

Run `grep -c 'msgstr ""' backend/locale/ar/LC_MESSAGES/django.po` to verify count. Current breakdown:

| App                 | Empty msgids |
|---------------------|---|
| transactions        | 75 |
| settings_app        | 67 |
| recurring           | 45 |
| dashboard           | 43 |
| templates (shared)  | 33 |
| reports             | 28 |
| fee_presets         | 19 |
| auth_app            | 17 |
| investments         | 13 |
| accounts            | 8 |
| budgets             | 6 |
| push                | 6 |
| virtual_accounts    | 6 |
| people              | 5 |
| exchange_rates      | 2 |

Total: 373 untranslated strings.

## Approach

Split into ~3 sub-batches by app group to keep PRs reviewable:

- **Batch A**: transactions + dashboard + shared templates (~150 strings) — most user-visible
- **Batch B**: settings_app + recurring + reports + investments (~155 strings)
- **Batch C**: fee_presets + auth_app + accounts + budgets + push + virtual_accounts + people + exchange_rates (~70 strings)

Each batch:
1. `uv run python manage.py makemessages -l ar --no-wrap`
2. Manually translate the empty `msgstr` entries for the batch's apps
3. `uv run python manage.py compilemessages -l ar`
4. `make test` (no regressions in English mode)
5. Commit per batch

## Translation guidelines

- Use standard Egyptian/Modern Standard Arabic finance vocabulary (per #514).
- Do **NOT** machine-translate financial terms.
- Keep numbers Western (1234, not ١٢٣٤) per project decision.
- Preserve `%(variable)s` placeholders verbatim.

## Playwright smoke test (final acceptance gate)

After all 3 batches land, add `e2e/tests/test_arabic_smoke.py` covering:

1. Switch language to Arabic via `/settings`.
2. Visit each key page — `/`, `/transactions/new`, `/accounts`, `/budgets`, `/settings`, `/recurring`, `/reports`, `/people`.
3. For each: assert `<html lang="ar" dir="rtl">`, no English fallback strings present in `<main>` (regex assertion against a small allowlist of brand names + numbers).
4. Take screenshot per page and store under `e2e/screenshots/ar/` for visual review.

## Acceptance Criteria

- [x] All 373 long-tail strings translated (single batch — curated dict made splitting unnecessary). Coverage: transactions (75), settings_app (67), recurring (45), dashboard (44), shared templates (33), reports (28), fee_presets (19), auth_app (17), investments (13), accounts (8), budgets (6), push (6), virtual_accounts (6), people (5), exchange_rates (2).
- [x] Final `grep -c 'msgstr ""'` returns 1 (header block only).
- [x] `compilemessages` clean — only header-field warnings, no errors.
- [x] Playwright smoke test `e2e/tests/test_arabic_smoke.py` covers 8 pages (home, transactions, accounts, budgets, settings, recurring, reports, people); 9 tests passing in 15s. Asserts `<html lang="ar" dir="rtl">` and scans `<main>` for English fallbacks against a small allowlist.
- [x] No regression in English mode — 1833 backend tests passing; e2e arabic suite passing.

## Affected User Journeys

- All J-1..J-5 (Arabic locale): full UI rendered in Arabic post-merge.

## Dependencies

- #514 (first-pass translations + duplicate-msgid cleanup) — done.

## Progress Notes

- 2026-04-27: Created — follow-up to #514 first pass; 373 strings remaining across 15 apps.
- 2026-04-27: Completed — 373 translations applied via curated dict (single commit; sub-batch split unnecessary since no schema risk). Playwright smoke test `e2e/tests/test_arabic_smoke.py` walks 8 pages, captures screenshots in `e2e/screenshots/ar/` (gitignored). 1833 backend + 9 e2e arabic tests passing.
