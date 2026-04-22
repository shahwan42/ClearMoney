---
id: "098"
title: "Contextual feature hints"
type: improvement
priority: medium
status: done
created: 2026-03-31
updated: 2026-03-31
---

## Description

Only batch-entry has a dismissible first-time hint. Other features (budgets, people tracking, virtual accounts, recurring rules) have no introduction. New users don't discover these capabilities.

## Acceptance Criteria

- [x] Budgets page: "Set spending limits per category to stay on track" hint on first visit
- [x] People page: "Track loans and debts with friends and family" hint
- [x] Virtual Accounts page: "Create savings envelopes for your goals" hint
- [x] Recurring page: "Automate salary, subscriptions, and regular payments" hint
- [x] Each hint has a dismiss button (X) and "Got it" CTA
- [x] Dismissed state stored in localStorage (same pattern as batch-entry hint)
- [x] Hints only appear when the page has no data (empty state enhancement)
- [x] Accessible: `role="status"`, dismissible via keyboard
- [x] E2E test for hint appearing on first visit → dismissing → not showing again

## Technical Notes

- Reuse existing hint pattern from `transactions.html:66-79` (dismissal via localStorage)
- Create reusable hint partial: `backend/templates/components/_feature_hint.html`
- Parameters: `hint_key`, `title`, `description`, `cta_text`, `cta_url`
- Include in each feature page template with page-specific content

## Progress Notes

- 2026-03-31: Created — improves feature discoverability for new users
- 2026-04-22: Implemented reusable component and added hints to Budgets, People, Virtual Accounts, and Recurring pages. Added E2E tests and verified behavior.
