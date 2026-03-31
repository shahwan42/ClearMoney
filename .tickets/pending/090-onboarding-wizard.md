---
id: "090"
title: "Onboarding wizard for new users"
type: feature
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

New users land on an empty dashboard with a single "Add Your First Account" button and no guidance. Add a multi-step onboarding wizard that walks them through initial setup and introduces key features.

## Acceptance Criteria

- [ ] 3-step guided setup: create institution → add account → record first transaction
- [ ] Progress indicator showing current step (1/3, 2/3, 3/3)
- [ ] Each step explains why it matters ("Track your spending by adding an account")
- [ ] Skip option at every step for power users
- [ ] Feature introduction tooltips after setup: budgets, people tracking, virtual accounts
- [ ] Onboarding state persisted (don't show again after completion or skip)
- [ ] Empty states on feature pages link back to relevant onboarding step
- [ ] Service-layer tests for onboarding state tracking
- [ ] E2E test for full onboarding flow → dashboard populated

## Technical Notes

- Store onboarding state in `UserConfig` or new JSONB field on User
- Reuse existing institution/account/transaction create forms — embed in wizard template
- First-time detection: user has zero accounts → show wizard instead of empty state
- Feature hints: use localStorage for dismissal (same pattern as batch-entry hint)
- Template: `backend/templates/dashboard/_onboarding_wizard.html`

## Progress Notes

- 2026-03-31: Created — addresses empty first-run experience for new users
