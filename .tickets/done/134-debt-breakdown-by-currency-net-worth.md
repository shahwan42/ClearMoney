---
id: "134"
title: "Debt breakdown by currency in net worth dashboard"
type: improvement
priority: medium
status: done
created: 2026-04-18
updated: 2026-04-18
---

## Description

The net worth dashboard "Debt" card showed total debt as a single EGP-formatted value, hiding USD debt. This adds per-currency debt tracking (EGP + USD) and displays USD debt separately when non-zero.

## Acceptance Criteria

- [x] `NetWorthSummary` and `DashboardData` expose `debt_egp` and `debt_usd` fields
- [x] `compute_net_worth` populates debt fields per currency
- [x] Net worth template shows EGP debt as primary, USD debt below when non-zero

## Progress Notes

- 2026-04-18: Completed — Added debt_egp/debt_usd to types and services, updated _net_worth.html template; also applied ruff formatting to reports/services.py, reports/tests/test_fees.py, transactions/views.py
