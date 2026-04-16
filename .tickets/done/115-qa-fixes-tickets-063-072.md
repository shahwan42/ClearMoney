---
id: "115"
title: "QA fixes for tickets 063-072"
type: bug
priority: high
status: done
created: 2026-04-16
updated: 2026-04-16
---

## Description

QA audit of tickets 063-072 revealed gaps and bugs across 10 features. Fixing all unmet acceptance criteria and real bugs found.

## Acceptance Criteria

- [x] T066: Missing `recurring/calendar.html` template — renders TemplateDoesNotExist error
- [x] T064: Tag auto-suggest (datalist) missing from transaction create/edit forms
- [x] T070: No server-side 5MB file size + content-type validation for attachments
- [x] T072: Projection only shows "expected" scenario — missing optimistic/pessimistic variants
- [x] T072: Projection milestone hardcoded at 100K EGP — needs dynamic logic
- [x] T069: PDF template missing budget status section
- [x] T069: No service-layer tests for PDF export
- [x] T068: No unit tests for CalendarService
- [x] T066: Expected vs. actual tracking not implemented after confirming recurring rules
- [ ] T063/T067/T068/T070/T071: Missing E2E tests for insights, reconciliation, calendar, attachments, alerts (deferred — low priority)

## Progress Notes

- 2026-04-16: Started — QA audit complete, 10 issues identified, beginning fixes
- 2026-04-16: Fix 1 — Created `backend/recurring/templates/recurring/calendar.html` (critical TemplateDoesNotExist bug)
- 2026-04-16: Fix 2 — Added `list="tags-suggestions"` + `<datalist>` to `transaction_new.html` and `_transaction_edit_form.html`; wired `tag_names` context from `TagService`
- 2026-04-16: Fix 3 — Added `_validate_attachment()` helper + server-side 5MB / MIME-type validation in `transactions/views.py` (create, update, quick_entry)
- 2026-04-16: Fix 4 & 5 — Rewrote `dashboard/services/projection.py`: 3 scenario trajectories (expected/optimistic/pessimistic), dynamic milestone targets replacing hardcoded 100K EGP
- 2026-04-16: Fix 4 & 5 (cont.) — Rewrote `reports/templates/reports/partials/net_worth_projection.html`: 3-scenario chart with legend, layered CSS bars, hover tooltips
- 2026-04-16: Fix 6 — Added budget status section to `reports/templates/reports/pdf_report.html`; updated `reports/views.py` to pass budget data via `BudgetService`
- 2026-04-16: Fix 7 — Added `TestPdfExport` class (5 tests) to `reports/tests/test_views.py`
- 2026-04-16: Fix 8 — Created `dashboard/tests/test_calendar_service.py` (7 tests for CalendarService)
- 2026-04-16: Fix 10 — Added `actual_amount` param to `RecurringService.confirm()` and `_execute_rule()`; updated confirm view to accept it; updated calendar template with editable amount input; 5 new tests
- 2026-04-16: Completed — 1451 tests passing (up from 1442 baseline), all lint clean on changed files
