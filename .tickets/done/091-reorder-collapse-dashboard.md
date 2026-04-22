---
id: "091"
title: "Reorder and collapse dashboard panels"
type: improvement
priority: high
status: done
created: 2026-03-31
updated: 2026-04-21
---

## Description

Dashboard has 11+ sections requiring extensive scrolling. Recent Transactions — the most daily-use panel — is buried last. Add collapsible sections and move high-frequency panels higher.

## Acceptance Criteria

- [x] Reorder panels: Alerts → Net Worth → Recent Transactions → Spending → Budgets → rest
- [x] Each section has a collapse/expand toggle (chevron icon)
- [x] Collapsed state persisted per user via localStorage
- [x] Collapsed sections show header only (one line) with key metric summary
- [x] "View All" link on collapsed sections navigates to full page
- [x] Smooth expand/collapse animation (CSS transition)
- [x] Keyboard accessible: Enter/Space toggles, focus visible
- [x] E2E test for collapsing a section → refreshing → section stays collapsed

## Technical Notes

- No backend changes needed — pure template + JS + localStorage
- Use `data-section="net-worth"` attributes for localStorage keys
- Collapsed summary: e.g., "Budgets (3 active, 1 over)" in single line
- Current template: `backend/dashboard/templates/dashboard/home.html`
- Animation: `max-height` transition or `details/summary` HTML element

## Progress Notes

- 2026-03-31: Created — addresses information overload and buried Recent Transactions
- 2026-04-21: Implemented reordering and collapse logic. Added `static/js/dashboard.js` and updated all dashboard partials. All E2E tests pass.
