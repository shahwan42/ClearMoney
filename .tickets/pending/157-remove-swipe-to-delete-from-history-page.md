---
id: "157"
title: "Remove swipe-to-delete from history page"
type: improvement
priority: medium
status: pending
created: 2026-04-24
updated: 2026-04-24
---

## Description

The history page currently supports swipe-to-delete on transaction rows. The request is to remove that gesture entirely from the history experience and keep deletion available through explicit UI controls only.

Current state:
- Transaction rows on `backend/transactions/templates/transactions/_transaction_row.html` render `data-swipe-delete` on non-compact history rows
- `static/js/gestures.js` binds swipe-to-delete behavior to any row with `[data-swipe-delete]`
- `backend/transactions/templates/transactions/transactions.html` renders a swipe-discovery hint
- Completed tickets `103`, `105`, and `106` improved the swipe-delete flow, so this ticket is a follow-on UX reversal rather than a net-new deletion feature

## Acceptance Criteria

- [ ] History page transaction rows no longer expose swipe-to-delete behavior
- [ ] Swipe hint text is removed from the history page
- [ ] Transaction deletion remains available through an explicit non-gesture control already present on the row
- [ ] No dashboard or compact transaction rows regress as a side effect
- [ ] Mobile interaction tests are updated to reflect the removal of swipe-to-delete
- [ ] Documentation describing swipe-to-delete on the history page is updated or removed where applicable

## Technical Notes

- Primary template touchpoints are likely `backend/transactions/templates/transactions/_transaction_row.html` and `backend/transactions/templates/transactions/transactions.html`
- `static/js/gestures.js` may still be needed for pull-to-refresh, so removal should be scoped to swipe-delete behavior rather than deleting the whole module blindly
- Review `backend/transactions/tests/test_swipe_discovery.py` and any E2E/manual QA docs that still assume swipe deletion exists

## Progress Notes

- 2026-04-24: Created from backlog request. Confirmed the current history page still renders `data-swipe-delete`, a swipe hint, and shared gesture handling in `static/js/gestures.js`.
