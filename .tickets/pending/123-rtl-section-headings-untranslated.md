---
id: "123"
title: "RTL/Arabic: Dashboard and Settings section headings not translated"
type: bug
priority: medium
status: pending
created: 2026-04-17
updated: 2026-04-17
---

## Description

When switching to Arabic (RTL) mode, the page layout correctly flips and some UI text is translated (category names, bottom nav labels), but several section headings and contextual strings remain in English.

## Untranslated Strings Observed (in Arabic mode)

**Dashboard (`/`):**
- "NET WORTH" → not translated
- "THIS MONTH VS LAST" → not translated
- "SPENDING PACE" → not translated  
- "BY CATEGORY" → not translated
- "CREDIT CARDS" → not translated
- "Manage" (button) → not translated
- "[Account name] has never been reconciled" → not translated

**Settings (`/settings`):**
- "DARK MODE" → not translated
- "LANGUAGE" → not translated
- "EXPORT TRANSACTIONS" → not translated
- "IMPORT TRANSACTIONS" → not translated
- "PUSH NOTIFICATIONS" → not translated
- "CATEGORIES" → not translated
- "TAGS" → not translated

## Additional RTL Bug: Text Fragmentation in Spending Pace

The "13 d left" label renders as **"d left 13"** in RTL mode — the number and unit are split across bidi boundary, producing nonsensical output.

**Screenshot:** `.tickets/attachments/qa-16-dashboard-rtl.png`

## Acceptance Criteria

- [ ] All dashboard section headings added to translation files (`locale/ar/LC_MESSAGES/django.po`)
- [ ] All settings section headings translated
- [ ] "never been reconciled" notification text translated
- [ ] Spending pace "X d left" fixed using proper bidi-safe formatting (e.g. `{% blocktrans %}{{ days }} days left{% endblocktrans %}` instead of concatenation)

## Progress Notes

- 2026-04-17: Filed during manual QA session (ticket #117). Screenshots: qa-15, qa-16.
