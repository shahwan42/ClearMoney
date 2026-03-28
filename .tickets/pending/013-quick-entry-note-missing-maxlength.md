---
id: "013"
title: "Quick-entry note input missing maxlength"
type: bug
priority: low
status: pending
created: 2026-03-28
updated: 2026-03-28
---

## Description

The note input in `_quick_entry.html` (line 74) is missing `maxlength="500"`. The full transaction form (`transaction_new.html`) has it, but quick-entry does not. This could allow users to submit notes longer than the DB column allows.

## Acceptance Criteria

- [ ] `_quick_entry.html` note input has `maxlength="500"`
- [ ] Matches the constraint in `transaction_new.html`

## Progress Notes

- 2026-03-28: Created — found during QA of Ticket #012
