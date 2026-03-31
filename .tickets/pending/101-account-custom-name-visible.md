---
id: "101"
title: "Account custom name always visible"
type: improvement
priority: low
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

The account custom name field is hidden behind a "Custom name" toggle button that most users won't discover. Make it always visible on the account creation/edit form.

## Acceptance Criteria

- [ ] Custom name input always visible on account form (no toggle to reveal)
- [ ] Field labeled "Display Name (optional)" with placeholder "e.g., Main Savings"
- [ ] Pre-filled with account type name as default suggestion
- [ ] Works for both create and edit flows
- [ ] E2E test for creating account with custom name

## Technical Notes

- Template: `backend/accounts/templates/accounts/_account_form.html:53-63`
- Remove the toggle button and `style="display: none"` on the input
- Make field optional (empty = use default type name, same as current behavior)
- Simple template change — no backend modification needed

## Progress Notes

- 2026-03-31: Created — improves discoverability of account naming
