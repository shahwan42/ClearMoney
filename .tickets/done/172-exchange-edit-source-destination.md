---
id: "172"
title: "Exchange edit: allow changing source and destination accounts"
type: feature
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Exchange transaction editing is too restrictive — source and destination accounts are read-only. Users cannot fix an exchange recorded to the wrong account. This ticket adds full account reassignment to the exchange edit form, with balance reconciliation.

## Acceptance Criteria

- [x] Source account dropdown shown in exchange edit form (non-dormant accounts only)
- [x] Destination account dropdown shown, filtered to accounts with different currency from source
- [x] Changing source account triggers HTMX re-render: destination list updates, rate label updates, rate/counter_amount cleared if currency pair changed
- [x] Rate label is dynamic: `{dest_currency} per 1 {src_currency}` (not hardcoded "EGP per 1 USD")
- [x] Same-currency validation error if source and destination have same currency at submit
- [x] `update_exchange()` service accepts optional `source_id` / `dest_id` params; performs undo/redo balance reconciliation when accounts change
- [x] All existing exchange edit tests still pass
- [x] New service tests: account reassignment (same pair, different pair, same-currency rejection)
- [x] New view tests: form renders account dropdowns, HTMX re-render endpoint, submit with account change

## Progress Notes

- 2026-04-27: Started — Designing exchange edit account reassignment feature
- 2026-04-27: Completed — Rewrote update_exchange() with debit/credit normalization + undo/redo balance reconciliation; added HTMX dest partial endpoint; rewrote exchange edit form section with source/dest dropdowns; fixed latent normalization bug; fixed credit-leg form display bug; 9 new tests (6 service + 9 view), all passing
