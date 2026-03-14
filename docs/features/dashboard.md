# Dashboard

The dashboard is the home page of ClearMoney, aggregating data from 10+ sources into a single view. It provides a complete financial snapshot at a glance.

## What It Shows

| Section | Description |
|---------|-------------|
| **Net Worth** | Total across all accounts with 30-day sparkline trend |
| **Month-over-Month Spending** | Current vs previous month with percentage change |
| **Spending Velocity** | Daily spending rate projection for the month |
| **Budget Progress** | Category bars (green/amber at 80%/red at 100%) |
| **Virtual Fund Balances** | Envelope allocation overview |
| **Credit Card Summary** | Utilization rings, payment due dates, minimum payments |
| **Account Health Warnings** | Accounts below minimum balance or missing deposits |
| **People Summary** | Outstanding loans/debts |
| **Habit Streak** | Consecutive days with logged transactions |
| **Recent Transactions** | Last entries with type-colored amounts |

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
  - `virtualFundSvc` — envelope fund balances
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
12. Loads virtual fund balances
13. Loads budgets with spending progress
14. Checks account health warnings

All optional data sources use nil-safe checks — if a service isn't wired, that section is simply empty.

### DashboardData View Model

**File:** `internal/service/dashboard.go` (line ~47)

The `DashboardData` struct has ~47 fields organized into sections:

- **Net worth:** `NetWorth`, `NetWorthEGP`, `ExchangeRate`, `USDTotal`, `USDInEGP`
- **Breakdown:** `CashTotal`, `CreditUsed`, `CreditAvail`, `DebtTotal`
- **Institutions:** `Institutions []InstitutionGroup` (with nested accounts)
- **People:** `PeopleOwedToMe`, `PeopleIOwe`
- **Investments:** `InvestmentTotal`
- **Credit cards:** `DueSoonCards`, `CreditCards []CreditCardSummary`
- **Streak:** `Streak StreakInfo`
- **Recent tx:** `RecentTransactions`
- **Trends:** `NetWorthHistory`, `NetWorthChange`, `ThisMonthSpending`, `LastMonthSpending`, `SpendingChange`, `TopCategories`
- **Velocity:** `SpendingVelocity` (pace indicator)
- **Account sparklines:** `AccountSparklines map[string][]float64`
- **Virtual funds:** `VirtualFunds`
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
1. **Net Worth section** — sparkline + trend indicator
2. **Habit Streak** — consecutive days badge
3. **Month-over-Month Spending** — comparison with top 3 categories
4. **Spending Velocity** — progress bar with color-coded status
5. **Due Date Warnings** — credit card alerts
6. **Account Health Warnings** — min balance/deposit alerts
7. **Credit Cards** — mini utilization rings with due dates
8. **Summary Cards** — cash/credit/debt breakdown grid
9. **Budget Progress** — progress bars by category
10. **Virtual Funds** — horizontally scrolling fund cards
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
| Virtual fund progress | CSS `<div>` with computed width | Fund balance vs target |

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
dashboardSvc.SetVirtualFundService(virtualFundSvc)
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
