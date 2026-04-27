---
id: "504"
title: "Recurring form: remove Exchange tab, auto-detect from currencies"
type: improvement
priority: medium
status: wip
created: 2026-04-27
updated: 2026-04-27
---

## Description

The recurring automation form has a separate "Exchange" tab, but Quick Entry has only a "Transfer" tab — exchange is auto-detected when source/dest currencies differ. Apply the same pattern to the recurring form.

## Acceptance Criteria

- [ ] No "Exchange" tab in the type radio group (Expense / Income / Transfer only)
- [ ] When Transfer selected and dest account chosen with different currency, exchange rate field appears automatically
- [ ] When Transfer selected and dest account has same currency, no exchange rate field
- [ ] Auto-confirm toggle disabled when currencies differ (exchange needs manual rate confirmation)
- [ ] Service `build_template_transaction` auto-sets type="exchange" when source/dest currencies differ
- [ ] Edit mode: existing exchange rules display with Transfer tab selected (correct round-trip)

## Progress Notes

- 2026-04-27: Started — removing Exchange tab, adding currency-diff detection in JS and service layer
- 2026-04-27: Completed — Exchange tab removed, service auto-detects exchange from currencies, JS shows rate field + disables auto-confirm when currencies differ, edit mode maps exchange→transfer radio
