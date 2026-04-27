---
id: "167"
title: "Dormant accounts enforcement"
type: improvement
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Dormant accounts exist in the model but enforcement was incomplete. Several places still included dormant accounts in calculations, UI, and forms as if they were active.

## Acceptance Criteria

- [x] Dormant CCs completely hidden from dashboard Credit Cards card (due dates, utilization, due-soon strip)
- [x] Dormant accounts excluded from credit metrics (credit_used, credit_available) — but still included in net worth
- [x] Account listing shows dormant badge next to account name + dormant accounts grouped at bottom of institution card
- [x] Health rule form shown but fully disabled (grayed out) with "Account is dormant" notice for dormant accounts
- [x] Account detail fully locked for dormant accounts (all edit fields disabled) — only "Activate" toggle remains active
- [x] Dormant accounts excluded from transaction/transfer account dropdowns (already filtered in helpers.py)
- [x] Toggle (both directions) requires confirmation dialog

## Progress Notes

- 2026-04-27: Started — Design decisions finalized via grill-me session
- 2026-04-27: Completed — 7 new tests, all 1639 passing, zero lint errors
