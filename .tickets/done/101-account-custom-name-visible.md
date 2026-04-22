---
id: "101"
title: "Account custom name always visible"
type: improvement
priority: low
status: done
created: 2026-03-31
updated: 2026-04-22
---

## Description

The account custom name field is hidden behind a "Custom name" toggle button that most users won't discover. Make it always visible on the account creation/edit form.

## Acceptance Criteria

- [x] Custom name input always visible on account form (no toggle to reveal)
- [x] Field labeled "Display Name (optional)" with placeholder "e.g., Main Savings"
- [x] Pre-filled with account type name as default suggestion
- [x] Works for both create and edit flows
- [x] E2E test for creating account with custom name

## Technical Notes

- Template: `backend/accounts/templates/accounts/_account_form.html:53-63`
- Remove the toggle button and `style="display: none"` on the input
- Make field optional (empty = use default type name, same as current behavior)
- Simple template change — no backend modification needed (Modified backend to support optional name in update flow too)

## Progress Notes

- 2026-03-31: Created — improves discoverability of account naming
- 2026-04-22: Implemented always-visible "Display Name (optional)" field in all account forms. Updated `AccountService.update` to handle empty names (auto-generation). Added E2E test for clearing name in edit mode.
