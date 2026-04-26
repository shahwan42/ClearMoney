---
id: "158"
title: "Refactor New budget form to bottom sheet"
type: improvement
priority: medium
status: done
created: 2026-04-24
updated: 2026-04-26
---

## Description

The budgets page currently renders the "New Budget" form inline as a full card near the top of `backend/budgets/templates/budgets/budgets.html`. Refactor that create flow to use the app's shared bottom-sheet pattern instead, so budget creation matches other mobile-first entry flows and reduces vertical clutter on the budgets page.

Current state:
- The budgets page shows the full create form inline with category, monthly limit, currency, rollover toggle, max carryover, and submit button
- The app already has a shared bottom-sheet component in `backend/templates/components/bottom_sheet.html` with behavior in `static/js/bottom-sheet.js`
- Other creation and edit flows already use bottom sheets, so this ticket is primarily a UX consistency and layout cleanup change rather than a new capability

## Acceptance Criteria

- [x] The inline "New Budget" form is replaced by a clear trigger that opens a bottom sheet
- [x] The budget create form renders inside a bottom sheet using the existing shared sheet pattern
- [x] All current create-budget fields and validation behavior remain available in the bottom sheet
- [x] Successful budget creation preserves the current post-submit behavior and updates the budgets UI correctly
- [x] The "Copy last month" action remains available in an appropriate location on the budgets page
- [x] Mobile and keyboard interaction for the new sheet flow are covered by tests or existing tests are updated
- [x] Budgets page documentation is updated if it still describes the create form as inline

## Technical Notes

- Primary template touchpoint is `backend/budgets/templates/budgets/budgets.html`
- Reuse `backend/templates/components/bottom_sheet.html` and `static/js/bottom-sheet.js` rather than introducing a budgets-specific modal pattern
- Consider whether the create form should be extracted into a reusable partial for HTMX-loaded sheet content or rendered inline inside a persistent sheet container
- Review budgets view coverage in `backend/budgets/tests/` and any docs under `docs/features/budgets.md` or route references that mention the inline form

## Progress Notes

- 2026-04-24: Created from backlog request. Confirmed the budgets page currently renders the full create form inline in `backend/budgets/templates/budgets/budgets.html` and the app already ships a shared bottom-sheet component suitable for this flow.
- 2026-04-26: Refactored form to bottom sheet. Extracted form to partial, added view/URL, updated main page and tests. All tests passed.
