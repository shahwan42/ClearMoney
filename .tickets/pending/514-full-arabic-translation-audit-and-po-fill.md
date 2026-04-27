---
id: "514"
title: "Full Arabic translation audit + .po fill"
type: improvement
priority: medium
status: pending
created: 2026-04-27
updated: 2026-04-27
---

## Description

Run `makemessages` to extract all current `{% trans %}` / `{% blocktrans %}` strings from templates and Python files. Audit the resulting `.po` file for missing Arabic translations (`msgstr ""`). Fill all gaps with accurate Arabic translations. Recompile `.mo`. Verify UI renders correctly in Arabic mode end-to-end.

## Steps

### 1. Extract all strings
```bash
cd backend
uv run python manage.py makemessages -l ar --no-wrap
```

This updates `backend/locale/ar/LC_MESSAGES/django.po` with any new strings added since last extraction.

### 2. Audit gaps
```bash
grep -c 'msgstr ""' backend/locale/ar/LC_MESSAGES/django.po
```

List all untranslated strings — these are the gaps to fill.

### 3. Fill translations

For each `msgstr ""` block, provide accurate Arabic translation. Key areas likely to have gaps:
- New template strings added in recent tickets (automations, pots, notifications, reports)
- Error messages from service layer (`_()` wrapped strings)
- Form labels and validation messages
- Push notification titles/bodies
- CSV export headers

### 4. Recompile
```bash
cd backend
uv run python manage.py compilemessages
```

Verifies `.po` is valid and generates `.mo` binary.

### 5. Smoke test UI in Arabic mode

Using Playwright, navigate key pages in Arabic mode and verify:
- No English strings leaking through in UI (all labels/buttons/headings are Arabic)
- RTL layout intact
- No `msgid` fallbacks visible (which would show raw English key if translation missing)

## Key Pages to Verify

- `/` dashboard — all panel headings, labels
- `/transactions/new` — form labels, submit button, validation errors
- `/accounts` — account type labels, balance display
- `/budgets` — budget form, progress labels
- `/settings` — language toggle, currency picker, category manager
- `/recurring` — automation form labels
- `/reports` — chart labels, filter controls
- `/people` — person form, loan labels

## Acceptance Criteria

- [ ] `makemessages` run — `.po` file is up to date with all current strings
- [ ] Zero `msgstr ""` entries in final `.po` file (all strings have Arabic translation)
- [ ] `compilemessages` completes without errors
- [ ] Playwright smoke test: 8 key pages pass visual check in Arabic mode
- [ ] No regression in English mode
- [ ] `make test && make lint` pass

## Dependencies

- Tickets #507–#513 should be complete first (they add new translatable strings that need to be included in this audit)

## Notes

- Do NOT use machine-translated Arabic for financial terms — use standard Egyptian/Modern Standard Arabic finance vocabulary
- Numbers stay Western (1234, not ١٢٣٤) per design decision
- Dates use Gregorian calendar formatted per Django's `DATE_FORMAT` for `ar` locale

## Progress Notes

- 2026-04-27: Created — Phase 4 full translation audit ticket
