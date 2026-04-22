---
id: "149"
title: "Dynamic reports filters and exact-currency reporting"
type: feature
priority: medium
status: pending
created: 2026-04-22
updated: 2026-04-22
---

## Description

Ticket `#139` made the main reports filter use dynamic currency options and
selected-currency defaults. This ticket completes the reports-side generalization
so queries, partials, and exports behave consistently for arbitrary active
currencies with no cross-currency consolidation.

## Details

- Audit all report queries and partials for hidden `EGP` / `USD` assumptions
- Ensure exact-currency filtering works for any active currency
- Keep PDF export aligned with on-screen report currency semantics
- Remove report-side `EGP` fallback behavior that overrides explicit selection
- Document any remaining legacy FX-specific report behavior separately

## Acceptance Criteria

- [ ] Reports support a third currency across queries and partials
- [ ] Report defaults resolve from the selected display currency consistently
- [ ] PDF export matches the on-screen report currency
- [ ] No report path silently converts or re-buckets currencies

## Critical Files

- `backend/reports/views.py`
- `backend/reports/services.py`
- `backend/reports/templates/reports/reports.html`
- `backend/reports/templates/reports/pdf_report.html`
- `backend/reports/templates/reports/partials/`

## Unit Tests

- Report filtering in a third currency
- Default-filter resolution from selected display currency
- PDF export consistency for non-USD/EGP currencies

## E2E Tests

- Render reports for `EUR`
- Export a PDF report for `EUR`
- Switch the header currency and confirm report defaults follow it

## Dependencies

- Depends on `#140`
- Depends on `#141`

## Progress Notes

- 2026-04-22: Created for full reports-side multi-currency support

