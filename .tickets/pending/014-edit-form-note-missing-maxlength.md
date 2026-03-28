---
id: "014"
title: "Edit form note input missing maxlength"
type: bug
priority: low
status: pending
created: 2026-03-28
updated: 2026-03-28
---

## Description

The note input in `_transaction_edit_form.html` (line 36) is missing a `maxlength` attribute. The full transaction form has `maxlength="500"`, but the edit form does not.

## Acceptance Criteria

- [ ] `_transaction_edit_form.html` note input has `maxlength="500"`

## Progress Notes

- 2026-03-28: Created — found during QA of Ticket #012
