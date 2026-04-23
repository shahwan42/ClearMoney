---
id: "141"
title: "Complete selected-currency plumbing rollout"
type: improvement
priority: high
status: done
created: 2026-04-22
updated: 2026-04-23
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

- [x] All major pages can access the effective selected display currency through
      one canonical path
- [x] HTMX and full-page flows preserve the selected display currency correctly
- [x] Invalid stored display-currency preferences recover cleanly
- [x] Remaining local `EGP` display-currency fallbacks are removed or justified
- [x] Single-currency users get a clean, stable experience

## Critical Files

- `backend/core/context_processors.py`
- `backend/templates/components/header.html`
- `backend/settings_app/views.py`
- `backend/dashboard/views.py`
- `backend/reports/views.py`
- `backend/people/views.py`
- `backend/budgets/views.py`

## Unit Tests

- Effective selected-currency resolution now goes through
  `get_user_display_currency_context(...)`
- Invalid preference recovery is covered in both currency helper tests and the
  shared context processor tests
- Context propagation into standard template responses and HTMX budget partials
  is covered
- View-level fallback behavior for one-currency users is covered via effective
  resolver tests and page-level selected-option assertions

## E2E Tests

- Change header currency and navigate across dashboard, reports, people, and budgets
- Reload after changing the header selector and confirm the selection persists
- Exercise partial updates and confirm they continue using the selected currency

Not added in this ticket. Coverage was extended at the unit/view layer and the
full backend pytest suite was run successfully.

## Dependencies

- Depends on `#139`

## Progress Notes

- 2026-04-22: Created after the foundation selector landed in `#139`
- 2026-04-23: Added `get_user_display_currency_context(...)` as the canonical
  selected-currency resolver and threaded it through shared template context,
  settings, budgets, reports, header, and investment form defaults
- 2026-04-23: Removed report template display-currency fallbacks that silently
  assumed `EGP`, while keeping safe fallback behavior for sparse registry state
  and single-currency users
- 2026-04-23: Added regression coverage for invalid stored preferences,
  effective selected-currency propagation, and HTMX total-budget responses;
  verified with targeted selected-currency tests and full backend `make test`
  with 1537 tests passing
- 2026-04-23: Completed — selected display currency now resolves through one
  canonical path across the remaining rollout surfaces, ticket moved to done
