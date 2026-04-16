---
id: "069"
title: "PDF report export"
type: feature
priority: low
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

Generate printable monthly PDF reports with income/expense summary, top categories, and budget status. Extends existing CSV export.

## Acceptance Criteria

- [ ] "Download PDF" button on reports page
- [ ] PDF contains: month summary, top 5 expense categories, budget status, net worth
- [ ] Clean layout suitable for printing
- [ ] Optional: email PDF report via existing `EmailService`
- [ ] Date range selection (default: current month)
- [ ] Service-layer tests for PDF data assembly
- [ ] E2E test for download button triggers file download

## Technical Notes

- Use `weasyprint` or `reportlab` for PDF generation
- Add dependency to `backend/pyproject.toml`
- Reuse existing `reports/services.py` data methods
- New endpoint: `GET /export/report-pdf?month=2026-03` in `settings_app`
- PDF template: HTML template rendered by weasyprint (reuse report layout)

## Progress Notes

- 2026-03-31: Created — planned as Tier 2 feature recommendation
