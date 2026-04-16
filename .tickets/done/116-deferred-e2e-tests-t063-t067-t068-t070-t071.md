---
id: "116"
title: "Deferred E2E tests for T063 T067 T068 T070 T071"
type: test
priority: medium
status: done
created: 2026-04-17
updated: 2026-04-17
---

## Description

Implement the 5 deferred E2E tests from the Tickets 063-072 QA audit. These were
marked low-priority and deferred from the main QA fix session (Ticket #115).

## Acceptance Criteria

- [x] T063: Reports insights navigation — verify 3m/6m/12m period selector + Spending Insights section renders
- [x] T067: Reconciliation workflow — navigate to reconcile page, select transactions, complete reconciliation
- [x] T068: Financial calendar — navigate to /calendar, month heading renders, prev/next navigation works
- [x] T070: Transaction attachments — upload PNG receipt, verify stored in DB and visible in detail, delete attachment
- [x] T071: Smart alerts — budget at 80%+ generates warning notification via /api/push/check

## Progress Notes

- 2026-04-17: Started — Researching selectors for all 5 test areas (reconcile, calendar, insights, attachments, alerts)
- 2026-04-17: Discovered `InvalidStorageError` — `STORAGES` dict in settings.py was missing `'default'` key, causing 500 on file upload
- 2026-04-17: Fixed `STORAGES` in `backend/clearmoney/settings.py` to include `FileSystemStorage` as default backend
- 2026-04-17: Fixed hx-boost issue — `transaction_new.html` boosted form returns partial HTML, causing HTMX to fall back to full reload; switched attachment tests to use `page.request.post()` directly
- 2026-04-17: Fixed insights URL assertions — reports selector adds full params (year, month, currency) to URL, not just months=; used `re.compile` pattern matching
- 2026-04-17: Fixed calendar navigation — added `page.wait_for_url()` after prev/next month clicks for HTMX navigation
- 2026-04-17: Fixed calendar transaction event — event title is the note ("Groceries"), not the category name ("Food")
- 2026-04-17: Completed — 192 E2E tests passing, 1451 unit tests passing
