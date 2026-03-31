---
id: "099"
title: "Budget save feedback"
type: improvement
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Inline budget edit (updating the monthly limit) has no success or error indication. Users can't tell if their change was saved. Add toast or inline confirmation.

## Acceptance Criteria

- [ ] After updating a budget limit: brief "Saved" text appears next to the field (green, fades after 2s)
- [ ] After updating total budget: same "Saved" confirmation
- [ ] On error: "Failed to save" message in red with retry hint
- [ ] Confirmation uses `aria-live="polite"` for screen reader announcement
- [ ] Visual feedback doesn't shift layout (use absolute positioning or reserved space)
- [ ] Works for both individual budget edit and total budget set
- [ ] E2E test for editing budget → "Saved" appears → fades

## Technical Notes

- Budget edit submits via standard POST with redirect to `/budgets`
- Option A: Change to HTMX submit (`hx-post`) and swap confirmation into result target
- Option B: Add query param `?saved=1` on redirect, show flash message
- Option A preferred — matches app's HTMX-first pattern
- Template: `backend/budgets/templates/budgets/budgets.html`

## Progress Notes

- 2026-03-31: Created — addresses missing feedback on budget inline edit
