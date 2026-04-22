---
id: "146"
title: "Dashboard selected-currency behavior"
type: feature
priority: high
status: pending
created: 2026-04-22
updated: 2026-04-22
---

## Description

Apply the header-selected display currency consistently to dashboard sections so
summary cards and drill-downs show exact-currency values only, with no
cross-currency conversion.

## Details

- Filter dashboard summary sections by the selected display currency
- Omit non-matching data instead of converting it
- Add explicit empty-state behavior when a selected currency has no data in a
  section
- Keep raw lists and account-native labels where the product still needs them,
  but ensure card totals follow selected-currency behavior

## Acceptance Criteria

- [ ] Changing the selected currency updates dashboard summaries
- [ ] Sections with no matching data show clear empty-state behavior
- [ ] No dashboard section silently converts values from other currencies
- [ ] Drill-down payloads remain consistent with the selected currency

## Critical Files

- `backend/dashboard/views.py`
- `backend/dashboard/templates/dashboard/_net_worth.html`
- `backend/dashboard/templates/dashboard/_accounts.html`
- `backend/dashboard/templates/dashboard/_net_worth_breakdown.html`
- `backend/dashboard/templates/dashboard/_spending.html`
- `backend/dashboard/templates/dashboard/_budgets.html`

## Unit Tests

- Service-layer selected-currency filtering
- Empty-state behavior for no-data currencies
- Drill-down payload generation for selected-currency summaries

## E2E Tests

- Switch from `EGP` to `EUR` and verify dashboard cards change
- Select a currency with no data and verify empty-state handling
- Open dashboard drill-downs after switching currencies

## Dependencies

- Depends on `#141`
- Depends on `#144`
- Depends on `#145`

## Progress Notes

- 2026-04-22: Created for dashboard selected-currency rollout

