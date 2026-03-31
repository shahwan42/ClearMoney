---
id: "098"
title: "Contextual feature hints"
type: improvement
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Only batch-entry has a dismissible first-time hint. Other features (budgets, people tracking, virtual accounts, recurring rules) have no introduction. New users don't discover these capabilities.

## Acceptance Criteria

- [ ] Budgets page: "Set spending limits per category to stay on track" hint on first visit
- [ ] People page: "Track loans and debts with friends and family" hint
- [ ] Virtual Accounts page: "Create savings envelopes for your goals" hint
- [ ] Recurring page: "Automate salary, subscriptions, and regular payments" hint
- [ ] Each hint has a dismiss button (X) and "Got it" CTA
- [ ] Dismissed state stored in localStorage (same pattern as batch-entry hint)
- [ ] Hints only appear when the page has no data (empty state enhancement)
- [ ] Accessible: `role="status"`, dismissible via keyboard
- [ ] E2E test for hint appearing on first visit → dismissing → not showing again

## Technical Notes

- Reuse existing hint pattern from `transactions.html:66-79` (dismissal via localStorage)
- Create reusable hint partial: `backend/templates/components/_feature_hint.html`
- Parameters: `hint_key`, `title`, `description`, `cta_text`, `cta_url`
- Include in each feature page template with page-specific content

## Progress Notes

- 2026-03-31: Created — improves feature discoverability for new users
