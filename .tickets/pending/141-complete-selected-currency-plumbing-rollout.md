---
id: "141"
title: "Complete selected-currency plumbing rollout"
type: improvement
priority: high
status: pending
created: 2026-04-22
updated: 2026-04-22
---

## Description

Ticket `#139` introduced the persisted header display-currency selector and base
request context support. This ticket completes the rollout so remaining views
and flows consume one canonical selected-currency resolver instead of ad hoc
defaults or local assumptions.

## Details

- Audit views and service entry points that still choose a currency locally
- Standardize on one effective selected-currency resolver for templates and views
- Ensure selected-currency persistence survives all common navigation and HTMX
  partial-update flows
- Remove remaining places where `EGP` is used as a fallback instead of the user's
  selected display currency
- Define and document safe behavior for one-active-currency users and invalid
  stored preferences

## Acceptance Criteria

- [ ] All major pages can access the effective selected display currency through
      one canonical path
- [ ] HTMX and full-page flows preserve the selected display currency correctly
- [ ] Invalid stored display-currency preferences recover cleanly
- [ ] Remaining local `EGP` display-currency fallbacks are removed or justified
- [ ] Single-currency users get a clean, stable experience

## Critical Files

- `backend/core/context_processors.py`
- `backend/templates/components/header.html`
- `backend/settings_app/views.py`
- `backend/dashboard/views.py`
- `backend/reports/views.py`
- `backend/people/views.py`
- `backend/budgets/views.py`

## Unit Tests

- Effective selected-currency resolution
- Invalid preference recovery
- Context propagation into HTMX partials and standard template responses
- View-level fallback behavior for one-currency users

## E2E Tests

- Change header currency and navigate across dashboard, reports, people, and budgets
- Reload after changing the header selector and confirm the selection persists
- Exercise partial updates and confirm they continue using the selected currency

## Dependencies

- Depends on `#139`

## Progress Notes

- 2026-04-22: Created after the foundation selector landed in `#139`

