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

**File:** `internal/service/dashboard.go` — `GetDashboard()` (line ~289)

Net worth is the sum of `current_balance` across **all** accounts, regardless of type:

```
NetWorth = SUM(account.CurrentBalance) for ALL accounts
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

- **EGPTotal** — sum of balances for all EGP accounts
- **USDTotal** — sum of balances for all USD accounts

### Converted Net Worth (NetWorthEGP)

For a single-number comparison, all balances are converted to EGP using the latest exchange rate:

```
NetWorthEGP = EGPTotal + (USDTotal × ExchangeRate)
```

If no exchange rate is available, `NetWorthEGP` is 0 (not calculated).

**Example:**
```
EGPTotal:      80,000
USDTotal:       2,000
ExchangeRate:   50.0 (EGP per 1 USD)
─────────────────────
NetWorthEGP:  180,000
```

### Historical Net Worth (Sparkline)

Daily snapshots (via `SnapshotService`) record `NetWorthEGP` and `NetWorthRaw`. The dashboard displays a 30-day sparkline using the last 30 snapshots.

## How Liquid Cash Is Calculated

**File:** `internal/service/dashboard.go` — `GetDashboard()` (line ~289)

Liquid cash (`CashTotal`) is the sum of balances for all **non-credit** accounts:

```
CashTotal = SUM(account.CurrentBalance) for accounts WHERE NOT IsCreditType()
```

### Which Account Types Are Included

| Account Type | In CashTotal? | In CreditUsed? |
|-------------|---------------|-----------------|
| `savings`   | Yes           | No              |
| `current`   | Yes           | No              |
| `prepaid`   | Yes           | No              |
| `cash`      | Yes           | No              |
| `credit_card` | No         | Yes             |
| `credit_limit` | No        | Yes             |

The split is determined by `Account.IsCreditType()` in `internal/models/account.go`:

```go
func (a Account) IsCreditType() bool {
    return a.Type == AccountTypeCreditCard || a.Type == AccountTypeCreditLimit
}
```

### Related Credit Metrics

Credit accounts feed two separate metrics:

- **CreditUsed** — sum of credit account balances (negative values representing outstanding debt)
- **CreditAvail** — sum of available credit: `CreditLimit + CurrentBalance` per credit account

**Example:**
```
Savings:        50,000 EGP  → CashTotal
Current:        30,000 EGP  → CashTotal
Cash:            5,000 EGP  → CashTotal
CC (limit 100k): -20,000    → CreditUsed = -20,000, CreditAvail = 80,000
──────────────────────────
CashTotal:      85,000
CreditUsed:    -20,000
CreditAvail:    80,000
NetWorth:       65,000 (CashTotal + CreditUsed)
```

## How Spending Pace Is Calculated

**File:** `internal/service/dashboard.go` — `computeSpendingComparison()` (line ~587)

Spending Pace answers: "How much of last month's spending have I already used up this month?"

### Formula

```
Percentage = (TotalSpendingThisMonth / TotalSpendingLastMonth) × 100
```

Spending is summed across **all currencies**, with USD converted to EGP using the latest exchange rate:

```
TotalSpending = EGP expenses + (USD expenses × ExchangeRate)
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

The progress bar color indicates whether you're spending faster or slower than the calendar pace:

| Status | Condition | Meaning |
|--------|-----------|---------|
| **Green** | `Percentage ≤ DayProgress` | On pace or under — spending sustainably |
| **Amber** | `Percentage ≤ DayProgress + 10` | Slightly ahead — watch your spending |
| **Red** | `Percentage > DayProgress + 10` | Overspending pace — will exceed last month |

The template renders a progress bar with the spending percentage as the fill, and a vertical line marker showing the calendar day progress for visual comparison.

### Edge Cases

- **No expenses last month**: Percentage stays at 0% (can't divide by zero). The section still renders but shows "0% of last month spent".
- **No expenses at all**: The "This Month vs Last" section doesn't render (empty `SpendingByCurrency`), but the Spending Pace section still renders since it's gated on `DaysTotal > 0`.
- **No exchange rate**: USD amounts are added without conversion (1:1 fallback).

### SpendingVelocity Struct

```go
type SpendingVelocity struct {
    Percentage   float64 // current month total / last month total × 100
    DaysElapsed  int     // e.g., 15
    DaysTotal    int     // e.g., 31
    DaysLeft     int     // e.g., 16
    DayProgress  float64 // e.g., 48.4%
    Status       string  // "green", "amber", or "red"
}
```

## Architecture

### Data Flow

```
Repositories (10+) → DashboardService.GetDashboard() → PageHandler.Home() → home.html template
```

### DashboardService

**File:** `internal/service/dashboard.go`

The `DashboardService` struct (line ~156) is the core aggregator. It has:

- **3 required dependencies** (constructor-injected):
  - `institutionRepo` — loads institutions and their accounts
  - `accountRepo` — loads account balances
  - `txRepo` — loads recent transactions

- **8 optional dependencies** (setter-injected, nil-safe):
  - `exchangeRateRepo` — USD/EGP conversion
  - `personRepo` — people ledger (loans/debts)
  - `investmentRepo` — portfolio total
  - `streakSvc` — habit streak calculation
  - `snapshotSvc` — historical net worth + per-account sparklines
  - `virtualAccountSvc` — envelope virtual account balances
  - `budgetSvc` — budget progress with spending
  - `healthSvc` — account health constraint violations

### Key Method: `GetDashboard(ctx) → DashboardData`

Located at line ~224. This method:

1. Loads all institutions and their accounts
2. Computes net worth, cash/credit breakdown, USD conversion
3. Fetches exchange rate for multi-currency support
4. Loads people summary (owed to me / I owe)
5. Loads investment portfolio total
6. Loads habit streak (consecutive days + weekly count)
7. Loads recent transactions
8. Loads 30-day net worth history (via snapshots) for sparkline
9. Loads per-account 30-day balance histories for mini sparklines
10. Calls `computeSpendingComparison()` for month-over-month data
11. Loads credit card summaries with utilization and due dates
12. Loads virtual account balances
13. Loads budgets with spending progress
14. Checks account health warnings

All optional data sources use nil-safe checks — if a service isn't wired, that section is simply empty.

### DashboardData View Model

**File:** `internal/service/dashboard.go` (line ~47)

The `DashboardData` struct has ~47 fields organized into sections:

- **Net worth:** `NetWorth`, `NetWorthEGP`, `EGPTotal`, `USDTotal`, `ExchangeRate`, `USDInEGP`
- **Breakdown:** `CashTotal`, `CreditUsed`, `CreditAvail`, `DebtTotal`
- **Institutions:** `Institutions []InstitutionGroup` (with nested accounts)
- **People:** `PeopleOwedToMe`, `PeopleIOwe`
- **Investments:** `InvestmentTotal`
- **Credit cards:** `DueSoonCards`, `CreditCards []CreditCardSummary`
- **Streak:** `Streak StreakInfo`
- **Recent tx:** `RecentTransactions`
- **Trends:** `NetWorthHistory`, `NetWorthChange`, `SpendingByCurrency []CurrencySpending` (per-currency this/last month + top categories), `ThisMonthSpending`, `LastMonthSpending`, `SpendingChange`, `TopCategories` (legacy EGP-only fields)
- **Velocity:** `SpendingVelocity` (pace indicator)
- **Account sparklines:** `AccountSparklines map[string][]float64`
- **Virtual accounts:** `VirtualAccounts`
- **Budgets:** `Budgets []BudgetWithSpending`
- **Health:** `HealthWarnings`

## Handler

**File:** `internal/handler/pages.go`

### Routes

| Route | Handler | Purpose |
|-------|---------|---------|
| `GET /` | `Home()` | Full dashboard page |
| `GET /partials/recent-transactions` | `RecentTransactions()` | HTMX partial refresh |
| `GET /partials/people-summary` | `PeopleSummary()` | HTMX partial refresh |

### Home Handler (line ~367)

Calls `dashboardSvc.GetDashboard(ctx)`, renders the `"home"` template with DashboardData as `.Data`. Shows an empty state if no data exists.

## Templates

### Main Page

**File:** `internal/templates/pages/home.html` (~377 lines)

Structure:
1. **Net Worth section** — per-currency display (EGP · USD), sparkline + trend indicator
2. **Habit Streak** — consecutive days badge
3. **Month-over-Month Spending** — comparison with top 3 categories
4. **Spending Velocity** — progress bar with color-coded status
5. **Due Date Warnings** — credit card alerts
6. **Account Health Warnings** — min balance/deposit alerts
7. **Credit Cards** — mini utilization rings with due dates
8. **Summary Cards** — cash/credit/debt breakdown grid
9. **Budget Progress** — progress bars by category
10. **Virtual Accounts** — horizontally scrolling virtual account cards
11. **People Summary** — owed to me / I owe
12. **Investment Portfolio** — total with link
13. **Accounts by Institution** — collapsible sections with mini sparklines
14. **Recent Transactions** — latest entries

### Partials Used

| Partial | File | Purpose |
|---------|------|---------|
| `chart-sparkline` | `partials/chart-sparkline.html` | Inline SVG polyline sparkline |
| `chart-trend` | `partials/chart-trend.html` | Arrow (▲/▼) with % change |
| `due-date-warning` | `partials/due-date-warning.html` | Red CC due date alert |
| `summary-cards` | `partials/summary-cards.html` | 2×2 grid: cash/credit/debt |
| `people-summary` | `partials/people-summary.html` | Owed to me / I owe box |
| `recent-transactions` | `partials/recent-transactions.html` | Transaction feed list |

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

## Wiring (router.go)

**File:** `internal/handler/router.go` (lines ~129-206)

```go
// Constructor with required deps
dashboardSvc := service.NewDashboardService(institutionRepo, accountRepo, txRepo)

// Setter injection for optional deps
dashboardSvc.SetExchangeRateRepo(exchangeRateRepo)
dashboardSvc.SetPersonRepo(personRepo)
dashboardSvc.SetInvestmentRepo(investmentRepo)
dashboardSvc.SetStreakService(streakSvc)
dashboardSvc.SetSnapshotService(snapshotSvc)
dashboardSvc.SetVirtualAccountService(virtualAccountSvc)
dashboardSvc.SetBudgetService(budgetSvc)
dashboardSvc.SetAccountHealthService(healthSvc)
dashboardSvc.SetDB(db)
```

## SQL Queries

The dashboard relies on:
- Standard repository queries (GetAll, GetRecent, etc.)
- Direct SQL for spending comparison (`computeSpendingComparison`)
- Materialized views: `mv_monthly_category_totals`, `mv_daily_tx_counts`
- Snapshot queries for historical net worth and per-account balances

## Key Files

| File | Purpose |
|------|---------|
| `internal/service/dashboard.go` | DashboardService + DashboardData struct |
| `internal/handler/pages.go` | Home, RecentTransactions, PeopleSummary handlers |
| `internal/handler/router.go` | Service wiring and route registration |
| `internal/templates/pages/home.html` | Main dashboard template |
| `internal/templates/partials/chart-sparkline.html` | Sparkline SVG partial |
| `internal/templates/partials/chart-trend.html` | Trend arrow partial |
| `internal/templates/partials/summary-cards.html` | Cash/credit breakdown |
| `internal/templates/partials/recent-transactions.html` | Transaction feed |
| `internal/templates/partials/people-summary.html` | People ledger |
| `internal/templates/partials/due-date-warning.html` | CC due date alerts |

## For Newcomers

- The dashboard is **read-only** — it aggregates data, doesn't modify it.
- All optional services degrade gracefully (nil-safe). If you remove a service, that section just won't render.
- The setter injection pattern avoids growing the already-15-param PageHandler constructor.
- HTMX partials (`/partials/recent-transactions`, `/partials/people-summary`) exist for post-action refreshes (e.g., after creating a transaction via quick-entry).
- Template functions like `formatEGP`, `formatUSD`, `sparklinePoints`, `chartColor` are defined in `charts.go` and `templates.go`.

## Logging

**Page views:** `dashboard`

**Debug:**

- Dashboard source timing logs: institutions, exchange rate, people, virtual accounts, investments, streak, recent transactions, snapshots, health, budgets, spending comparison
