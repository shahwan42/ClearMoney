---
id: "151"
title: "Dashboard and historical sparkline consumption rewrite"
type: feature
priority: medium
status: pending
created: 2026-04-22
updated: 2026-04-22
---

## Description

Update dashboard sparkline consumers to use the generalized historical model
instead of fixed EGP/USD history keys and dual-series template assumptions.

## Details

- Replace fixed `EGP` / `USD` history lookups in dashboard services
- Update sparkline templates to consume selected-currency history dynamically
- Define explicit no-history behavior for currencies with no historical series
- Preserve room for future multi-series history views without blocking the
  selected-currency path

## Acceptance Criteria

- [ ] Dashboard net-worth history works for any active currency
- [ ] No sparkline template depends on fixed EGP/USD keys
- [ ] Currencies with no history show a clean empty-state behavior

## Critical Files

- `backend/dashboard/services/sparklines.py`
- `backend/dashboard/templates/dashboard/_net_worth.html`
- `backend/templates/components/chart_sparkline_dual.html`

## Unit Tests

- Selected-currency history extraction
- Missing-history handling
- Third-currency sparkline input generation

## E2E Tests

- Switch selected currency and verify sparkline changes
- Select a currency with no history and verify empty-state behavior

## Dependencies

- Depends on `#150`
- Depends on `#146`

## Progress Notes

- 2026-04-22: Created for dashboard history consumption updates

