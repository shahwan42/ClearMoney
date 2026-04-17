---
id: "123"
title: "RTL/Arabic: Dashboard and Settings section headings not translated"
type: bug
priority: medium
status: done
created: 2026-04-17
updated: 2026-04-17
---

## Description

When switching to Arabic (RTL) mode, the page layout correctly flips and some UI text is translated (category names, bottom nav labels), but several section headings and contextual strings remain in English.

## Untranslated Strings Observed (in Arabic mode)

**Dashboard (`/`):**
- "NET WORTH" → translated
- "THIS MONTH VS LAST" → translated
- "SPENDING PACE" → translated  
- "BY CATEGORY" → translated
- "CREDIT CARDS" → translated
- "Manage" (button) → translated
- "[Account name] has never been reconciled" → translated

**Settings (`/settings`):**
- "DARK MODE" → translated
- "LANGUAGE" → translated
- "EXPORT TRANSACTIONS" → translated
- "IMPORT TRANSACTIONS" → translated
- "PUSH NOTIFICATIONS" → translated
- "CATEGORIES" → translated
- "TAGS" → translated

## Additional RTL Bug: Text Fragmentation in Spending Pace

The "13 d left" label renders as **"d left 13"** in RTL mode — the number and unit are split across bidi boundary, producing nonsensical output.

**Screenshot:** `.tickets/attachments/qa-16-dashboard-rtl.png`

## Acceptance Criteria

- [x] All dashboard section headings added to translation files (`locale/ar/LC_MESSAGES/django.po`)
- [x] All settings section headings translated
- [x] "never been reconciled" notification text translated
- [x] Spending pace "X d left" fixed using proper bidi-safe formatting (e.g. `{% blocktrans %}{{ days }} days left{% endblocktrans %}` instead of concatenation)

## Progress Notes

- 2026-04-17: Filed during manual QA session (ticket #117). Screenshots: qa-15, qa-16.
- 2026-04-17: Implemented all missing translations in `django.po`, recompiled messages, and fixed Spending Pace bidi issue in `_spending.html`.
