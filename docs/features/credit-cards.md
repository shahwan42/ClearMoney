# Credit Cards

ClearMoney has specialized support for credit card accounts including statement views, billing cycle tracking, utilization charts, interest-free period monitoring, and payment guidance.

## How Credit Cards Differ

Credit cards use the same `Account` model but with key differences:

- **Type:** `credit_card` or `credit_limit`
- **Balance is negative** — represents debt (e.g., -120,000 = 120K used)
- **CreditLimit field** — required for credit types, nullable for others
- **Metadata JSONB** — stores billing cycle info (statement_day, due_day)
- **Available credit** = `credit_limit + current_balance` (since balance is negative)

The `IsCreditType()` method identifies credit accounts. The `neg` template function flips the sign for display.

## Billing Cycle

### Data Storage

Billing cycle info is stored in the `metadata` JSONB column:

```json
{
  "statement_day": 15,
  "due_day": 5
}
```

### Types

**File:** `internal/service/account.go`

- `BillingCycleMetadata` (line ~43) — parsed from JSONB: `StatementDay`, `DueDay`
- `BillingCycleInfo` (line ~52) — computed for current period:
  - `PeriodStart`, `PeriodEnd` — current billing period dates
  - `DueDate` — when payment is due
  - `DaysUntilDue` — countdown (negative if overdue)
  - `IsDueSoon` — true if due within 7 days

### Functions

- `ParseBillingCycle(acc)` — unmarshals metadata JSONB
- `GetBillingCycleInfo(meta, now)` — computes current period dates based on today

## Statement View

**Route:** `GET /accounts/{id}/statement`

**Handler:** `CreditCardStatement()` in `pages.go`

### StatementData Struct

**File:** `internal/service/account.go` (line ~128)

- `Account` — the credit card
- `BillingCycle` — computed period info
- `Transactions` — all transactions in the billing period
- `OpeningBalance` — balance at period start (computed by subtracting all deltas from closing)
- `ClosingBalance` — current balance
- `TotalSpending` — sum of expenses
- `TotalPayments` — sum of credits/payments
- `InterestFreeDays`, `InterestFreeRemain`, `InterestFreeUrgent`
- `PaymentHistory` — recent payments to card

### Statement Fetching

`GetStatementData()` (line ~160):
1. Parses billing cycle from account metadata
2. Computes period dates (supports past periods via `?period=YYYY-MM` query param)
3. Loads transactions in the billing period
4. Computes opening balance by reversing deltas
5. Calculates interest-free period (55 days from statement close)
6. Loads recent payment history

## Interest-Free Period

Standard interest-free period is 55 days from statement close date.

```go
interestFreeEnd := info.PeriodEnd.AddDate(0, 0, 55)
remain := int(interestFreeEnd.Sub(now).Hours() / 24)
urgent := remain > 0 && remain <= 7
```

Displayed in the statement view with an urgency indicator when ≤ 7 days remain.

## Utilization

### Calculation

**File:** `internal/service/account.go` — `GetCreditCardUtilization()` (line ~245)

```go
used := -acc.CurrentBalance  // balance is negative, negate to get positive
return used / *acc.CreditLimit * 100
```

### Donut Chart

Displayed on the account detail page as an SVG circle using `stroke-dasharray`:

```html
<circle stroke-dasharray="{{.UtilizationPct}}, 100" />
```

Color thresholds:
- Green: < 50%
- Amber: 50-80%
- Red: > 80%

### Utilization Trends

Historical utilization computed from 30-day balance snapshots:

```go
for _, bal := range balanceHistory {
    used := -bal
    utilizationHistory = append(utilizationHistory, used / *acc.CreditLimit * 100)
}
```

Rendered as an SVG sparkline below the donut chart.

## Payment Guidance

Shown in the statement view when balance < 0:

- Shows full statement balance with `neg` function (displays positive amount)
- Due date from billing cycle info
- Days until due countdown
- Currently guidance is for full balance payment (no minimum payment logic)

## Fawry Cash-Out

**Service:** `internal/service/transaction.go` — `CreateFawryCashout()` (line ~504)

Converts credit card balance to prepaid cash:
1. Creates expense on credit card for (amount + fee)
2. Creates income on prepaid account for amount
3. Both linked via `LinkedTransactionID`
4. All within single DB transaction

**Handler:** `FawryCashout()` (GET) renders form, `FawryCashoutCreate()` (POST) processes it.

## Dashboard Integration

The dashboard shows credit cards with:
- Mini utilization rings (SVG with `stroke-dasharray`)
- Card name as clickable link
- Due date countdown (if billing cycle configured)
- Current balance (red if negative)
- Link to statement

## Templates

| Template | Purpose |
|----------|---------|
| `pages/account-detail.html` | Detail page with utilization donut, sparkline, billing info |
| `pages/credit-card-statement.html` | Statement view with period, interest-free tracker, payments |
| `partials/credit-card-info.html` | Billing cycle info box (statement day, period, due date) |

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/account.go` | Account model with IsCreditType(), AvailableCredit() |
| `internal/service/account.go` | BillingCycle parsing, StatementData, utilization calc |
| `internal/service/transaction.go` | Fawry cash-out logic |
| `internal/handler/pages.go` | AccountDetail, CreditCardStatement, FawryCashout handlers |
| `internal/handler/charts.go` | conicGradient template function for donut charts |
| `internal/templates/pages/credit-card-statement.html` | Statement template |
| `internal/templates/pages/account-detail.html` | Detail page with CC features |
| `internal/templates/partials/credit-card-info.html` | Billing cycle partial |

## For Newcomers

- **Balance sign convention** is the most common source of confusion. CC balances are always negative (debt). Use `neg` in templates to display as positive amounts.
- **Billing cycle metadata** is stored as JSONB, not as separate columns. This keeps the schema simple.
- **Interest-free period** is hardcoded at 55 days. Different banks may have different periods — this could be made configurable.
- **Utilization color thresholds** (50%/80%) are consistent across the donut chart, dashboard rings, and trend sparklines.
- **Statement periods** can be viewed historically via the `?period=YYYY-MM` query parameter.
