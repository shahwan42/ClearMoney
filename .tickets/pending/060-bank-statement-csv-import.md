---
id: "060"
title: "Bank statement CSV import"
type: feature
priority: high
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Add a CSV import wizard that lets users upload bank statement CSVs and bulk-create transactions. This eliminates the biggest friction point — manual data entry.

## Acceptance Criteria

- [ ] Upload form at `/settings/import` accepting `.csv` files
- [ ] Column mapping step: user maps CSV columns to transaction fields (date, amount, type, note)
- [ ] Preview step: show parsed rows before committing, highlight validation errors
- [ ] Auto-categorize notes using existing `suggest_category()` from `transactions/services/helpers.py`
- [ ] Duplicate detection by date + amount + note hash (warn, don't block)
- [ ] Batch create via existing `TransactionService.batch_create()`
- [ ] Summary page: created count, skipped count, error details
- [ ] Support ClearMoney's own export format as a preset mapping
- [ ] Service-layer tests for parsing, validation, duplicate detection
- [ ] E2E test for upload → preview → confirm → balance updated flow

## Technical Notes

- Add to `settings_app` (mirrors existing `/export/transactions`)
- Currency always overridden from account (never trust CSV currency column)
- Amount always positive; type determines debit/credit
- Use `transaction.atomic()` for the batch — all or nothing per import
- Max file size: 5MB / 10,000 rows

## Progress Notes

- 2026-03-31: Created — planned as Tier 1 feature recommendation
