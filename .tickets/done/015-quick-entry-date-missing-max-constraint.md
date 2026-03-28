---
id: "015"
title: "Quick-entry date picker allows future dates"
type: bug
priority: low
status: done
created: 2026-03-28
updated: 2026-03-28
---

## Description

The date picker in `_quick_entry.html` (line 92) is missing `max="{{ today|date:'Y-m-d' }}"`. The full transaction form has this constraint, but quick-entry does not, allowing users to select future dates.

## Acceptance Criteria

- [x] `_quick_entry.html` date picker has `max="{{ today|date:'Y-m-d' }}"`

## Progress Notes

- 2026-03-28: Created — found during QA of Ticket #012
- 2026-03-28: Started — implementing fix
- 2026-03-28: Completed — added max="{{ today|date:'Y-m-d' }}" to quick-entry date input
