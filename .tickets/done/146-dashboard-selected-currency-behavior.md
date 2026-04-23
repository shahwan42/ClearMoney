---
id: "146"
title: "Dashboard selected-currency behavior"
type: feature
priority: high
status: done
created: 2026-04-22
updated: 2026-04-23
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

- [x] Changing the selected currency updates dashboard summaries
- [x] Sections with no matching data show clear empty-state behavior
- [x] No dashboard section silently converts values from other currencies
- [x] Drill-down payloads remain consistent with the selected currency

## Critical Files

- `backend/dashboard/views.py`
- `backend/dashboard/templates/dashboard/_net_worth.html`
- `backend/dashboard/templates/dashboard/_accounts.html`
- `backend/dashboard/templates/dashboard/_net_worth_breakdown.html`
- `backend/dashboard/templates/dashboard/_spending.html`
- `backend/dashboard/templates/dashboard/_budgets.html`

## Unit Tests

- [x] Service-layer selected-currency filtering
- [x] Empty-state behavior for no-data currencies
- [x] Drill-down payload generation for selected-currency summaries

## E2E Tests

- [ ] Switch from `EGP` to `EUR` and verify dashboard cards change
- [ ] Select a currency with no data and verify empty-state handling
- [ ] Open dashboard drill-downs after switching currencies

## Dependencies

- Depends on `#141`
- Depends on `#144`
- Depends on `#145`

## Progress Notes

- 2026-04-22: Created for dashboard selected-currency rollout
- 2026-04-23: Implemented selected-currency filtering across all dashboard services and templates. Removed cross-currency conversion logic. Updated unit tests. All tests passing.
