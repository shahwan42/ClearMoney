# Dashboard

The dashboard is the home page of ClearMoney, aggregating data from 10+ sources into a single view. It provides a complete financial snapshot at a glance.

## What It Shows

| Section | Description |
|---------|-------------|
| **Net Worth** | Total across all accounts with 30-day sparkline trend |
| **Month-over-Month Spending** | Current vs previous month with percentage change |
| **Spending Pace** | How much of last month's total you've already spent, with days remaining |
| **Budget Progress** | Category bars (green/amber at 80%/red at 100%) |
| **Virtual Account Balances** | Envelope allocation overview |
| **Credit Card Summary** | Utilization rings, payment due dates, minimum payments |
| **Account Health Warnings** | Accounts below minimum balance or missing deposits |
| **People Summary** | Outstanding loans/debts |
| **Habit Streak** | Consecutive days with logged transactions |
| **Recent Transactions** | Last entries with type-colored amounts |

## How Net Worth Is Calculated

**File:** `backend/dashboard/services/__init__.py`

Net worth is the sum of `current_balance` across **all** accounts, regardless of type:

```
NetWorth = SUM(account.current_balance) for ALL accounts
```

This includes credit cards, which have negative balances (representing debt), so they reduce net worth.

**Example:**
```
Savings (EGP):     50,000
Current (EGP):     30,000
Credit Card (EGP): -20,000  ← negative = debt
Cash (USD):         2,000
─────────────────────────
NetWorth:          62,000   (mixed currencies — raw sum)
```

### Per-Currency Totals

The dashboard also tracks per-currency breakdowns:

- **egp_total** — sum of balances for all EGP accounts
- **usd_total** — sum of balances for all USD accounts

### Converted Net Worth (net_worth_egp)

For a single-number comparison, all balances are converted to EGP using the latest exchange rate:

```
net_worth_egp = egp_total + (usd_total × exchange_rate)
```

If no exchange rate is available, `net_worth_egp` is 0 (not calculated).

### Historical Net Worth (Sparkline)

Daily snapshots record `net_worth_egp` and `net_worth_raw`. The dashboard displays a 30-day sparkline using the last 30 snapshots.

## How Liquid Cash Is Calculated

`cash_total` is the sum of balances for all **non-credit** accounts:

```
cash_total = SUM(current_balance) for accounts WHERE type NOT IN ('credit_card', 'credit_limit')
```

### Which Account Types Are Included

| Account Type | In cash_total? | In credit_used? |
|-------------|----------------|-----------------|
| `savings`   | Yes            | No              |
| `current`   | Yes            | No              |
| `prepaid`   | Yes            | No              |
| `cash`      | Yes            | No              |
| `credit_card` | No           | Yes             |
| `credit_limit` | No          | Yes             |

### Related Credit Metrics

Credit accounts feed two separate metrics:

- **credit_used** — sum of credit account balances (negative values representing outstanding debt)
- **credit_avail** — sum of available credit: `credit_limit + current_balance` per credit account

**Example:**
```
Savings:        50,000 EGP  → cash_total
Current:        30,000 EGP  → cash_total
Cash:            5,000 EGP  → cash_total
CC (limit 100k): -20,000    → credit_used = -20,000, credit_avail = 80,000
──────────────────────────
cash_total:      85,000
credit_used:    -20,000
credit_avail:    80,000
net_worth:       65,000 (cash_total + credit_used)
```

## How Spending Pace Is Calculated

**File:** `backend/dashboard/services/__init__.py` — `_compute_spending_comparison()`

Spending Pace answers: "How much of last month's spending have I already used up this month?"

### Formula

```
percentage = (total_spending_this_month / total_spending_last_month) × 100
```

Spending is summed across **all currencies**, with USD converted to EGP using the latest exchange rate:

```
total_spending = EGP expenses + (USD expenses × exchange_rate)
```

If no exchange rate is available, USD amounts are added at face value (better than ignoring them).

### Example

```
This month (March, day 15 of 31):
  EGP expenses:  4,000
  USD expenses:    $80  × 50 (rate) = 4,000 EGP
  Total:         8,000 EGP-equivalent

Last month (February):
  EGP expenses:  6,000
  USD expenses:   $120  × 50 (rate) = 6,000 EGP
  Total:        12,000 EGP-equivalent

Percentage = 8,000 / 12,000 × 100 = 67%
Day progress = 15 / 31 × 100 = 48%

→ "67% of last month spent" with 16 days left
→ Status: RED (67% > 48% + 10%)
```

### Status Colors

| Status | Condition | Meaning |
|--------|-----------|---------|
| **Green** | `percentage ≤ day_progress` | On pace or under — spending sustainably |
| **Amber** | `percentage ≤ day_progress + 10` | Slightly ahead — watch your spending |
| **Red** | `percentage > day_progress + 10` | Overspending pace — will exceed last month |

### Edge Cases

- **No expenses last month**: Percentage stays at 0% (can't divide by zero). Section still renders showing "0% of last month spent".
- **No expenses at all**: The "This Month vs Last" section doesn't render, but Spending Pace still renders since it's gated on `days_total > 0`.
- **No exchange rate**: USD amounts are added without conversion (1:1 fallback).

## Architecture

### Data Flow

```
10+ queries → get_dashboard_data(user_id) → dashboard_page() view → home.html template
```

### Service

**File:** `backend/dashboard/services/__init__.py` — `get_dashboard_data(user_id)`

The function aggregates data from all sources:

1. Loads all institutions and their accounts
2. Computes net worth, cash/credit breakdown, USD conversion
3. Fetches exchange rate for multi-currency support
4. Loads people summary (owed to me / I owe)
5. Loads investment portfolio total
6. Loads habit streak (consecutive days + weekly count)
7. Loads recent transactions
8. Loads 30-day net worth history (via snapshots) for sparkline
9. Loads per-account 30-day balance histories for mini sparklines
10. Calls `_compute_spending_comparison()` for month-over-month data
11. Loads credit card summaries with utilization and due dates
12. Loads virtual account balances
13. Loads budgets with spending progress
14. Checks account health warnings

All optional data sources degrade gracefully — if data is missing, that section is simply empty.

## Views

**File:** `backend/dashboard/views.py`

### Routes

| Route | Handler | Purpose |
|-------|---------|---------|
| `GET /` | `dashboard_page()` | Full dashboard page |
| `GET /partials/recent-transactions` | `recent_transactions()` | HTMX partial refresh |
| `GET /partials/people-summary` | `people_summary()` | HTMX partial refresh |

## Templates

### Main Page

**File:** `backend/dashboard/templates/dashboard/home.html`

Structure (ordered by priority — actionable items first, reference data last):

1. **Alerts** — due date warnings + account health warnings (time-sensitive, shown first)
2. **Net Worth + Summary Cards** — per-currency totals, sparkline, trend, then 2×2 breakdown (cash/credit/debt)
3. **Month-over-Month Spending + Velocity** — comparison with top categories and spending pace bar
4. **Budget Progress** — progress bars by category
5. **Credit Cards** — mini utilization rings with due dates
6. **Virtual Accounts** — horizontally scrolling cards
7. **Accounts by Institution** — collapsible sections with mini sparklines
8. **People Summary** — owed to me / I owe (hidden when all balances are zero)
9. **Investment Portfolio** — total with link (hidden when zero)
10. **Habit Streak** — consecutive days badge
11. **Recent Transactions** — latest entries

### Partials Used

| Partial | Purpose |
|---------|---------|
| `chart-sparkline` | Inline SVG polyline sparkline |
| `chart-trend` | Arrow (▲/▼) with % change |
| `due-date-warning` | Red CC due date alert |
| `people-summary` | Owed to me / I owe box (per-currency) |
| `recent-transactions` | Transaction feed list |

## Charts on Dashboard

All charts are CSS-only (no JavaScript charting libraries):

| Chart | Technology | Data Source |
|-------|-----------|-------------|
| Net worth sparkline | Inline SVG `<polyline>` | 30-day snapshot history |
| Account mini sparklines | Inline SVG (48×16px) | Per-account 30-day snapshots |
| Spending velocity bar | CSS flexbox with `width: X%` | Current month spending rate |
| CC utilization rings | SVG `stroke-dasharray` | Credit limit vs balance |
| Budget progress bars | CSS `<div>` with computed width | Budget limit vs spending |
| Virtual account progress | CSS `<div>` with computed width | Virtual account balance vs target |

## Key Files

| File | Purpose |
|------|---------|
| `backend/dashboard/services/__init__.py` | `get_dashboard_data()` aggregator |
| `backend/dashboard/views.py` | `dashboard_page()`, `recent_transactions()`, `people_summary()` |
| `backend/dashboard/templates/dashboard/home.html` | Main dashboard template |

## For Newcomers

- The dashboard is **read-only** — it aggregates data, doesn't modify it.
- HTMX partials (`/partials/recent-transactions`, `/partials/people-summary`) exist for post-action refreshes (e.g., after creating a transaction via quick-entry).
- Template filters like `format_egp`, `format_usd`, `sparkline_points`, `chart_color` are in `core/templatetags/money.py`.

## Logging

**Page views:** `dashboard`

**Debug:**

- Dashboard source timing logs: institutions, exchange rate, people, virtual accounts, investments, streak, recent transactions, snapshots, health, budgets, spending comparison
