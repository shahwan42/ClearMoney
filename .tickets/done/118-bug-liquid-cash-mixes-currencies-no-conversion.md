---
id: "118"
title: "Bug: Liquid Cash dashboard card sums multi-currency balances without conversion"
type: bug
priority: high
status: done
created: 2026-04-17
updated: 2026-04-18
---

## Description

The **Liquid Cash** card on the dashboard incorrectly sums account balances across currencies without applying exchange rate conversion, producing a misleading total.

**Observed:** EGP 13,300 (Main Checking) + USD 500 (USD Account) = displayed as **EGP 13,800.00**  
**Expected:** USD balance should be converted to EGP using a stored exchange rate, OR shown as a separate per-currency sub-total.

## Root Cause

In `backend/dashboard/services/accounts.py`, `_transform_liquid_cash()` applies no transformation at all — the raw balance (regardless of currency) is passed straight through and summed. The Net Worth card correctly separates by currency; Liquid Cash does not.

```python
def _transform_liquid_cash(acc: Any, bal: float, row: dict[str, Any]) -> None:
    """No transformation needed — balance is used as-is."""  # BUG: ignores currency
    pass
```

## Steps to Reproduce

1. Create two accounts: one EGP (balance 13,300) and one USD (balance 500)
2. Navigate to `/` (dashboard)
3. Observe "Liquid Cash" card shows `EGP 13,800.00`
4. The 500 USD is treated as 500 EGP — no conversion applied

## Screenshot

See: `.tickets/attachments/qa-02-dashboard-with-data.png`

## Acceptance Criteria

- [x] Liquid Cash card shows per-currency sub-totals (matching Net Worth card behavior)
- [x] The displayed number must never mix raw balances from different currencies

## Progress Notes

- 2026-04-17: Filed during manual QA session (ticket #117). Verified via DB query — USD account balance 500 directly added to EGP total.
- 2026-04-18: Started — implementing per-currency split (cash_total=EGP only, cash_usd=USD) matching Net Worth card pattern.
- 2026-04-18: Completed — Added `cash_usd` field to `NetWorthSummary` and `DashboardData`; split `compute_net_worth()` to separate EGP/USD liquid cash; updated `_net_worth.html` to show USD sub-total when non-zero. 1470 tests pass.
