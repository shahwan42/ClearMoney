# People (Loans & Debts)

Track informal lending and borrowing with people. Record loans, borrowings, and repayments with automatic balance tracking and payoff projections.

## Concept

Each person has a `net_balance` that tracks the overall financial relationship:

- **Positive balance** = they owe you (you lent more than they repaid)
- **Negative balance** = you owe them (you borrowed more than you repaid)
- **Zero** = settled

## Model

**File:** `internal/models/person.go`

```go
type Person struct {
    ID         string
    Name       string
    Note       *string   // nullable
    NetBalance float64   // cached denormalized total
    CreatedAt  time.Time
    UpdatedAt  time.Time
}
```

`NetBalance` is a denormalized cache — updated atomically alongside transactions.

## Transaction Types for People

| Type | Direction | Account Effect | Person Effect |
|------|-----------|---------------|---------------|
| `loan_out` | You lend money | Account balance decreases | Person.NetBalance increases |
| `loan_in` | You borrow money | Account balance increases | Person.NetBalance decreases |
| `loan_repayment` | Someone repays | Auto-detected from current balance | Moves toward zero |

## Repository

**File:** `internal/repository/person.go`

| Method | Purpose |
|--------|---------|
| `Create(ctx, person)` | Insert person |
| `GetByID(ctx, id)` | Single person |
| `GetAll(ctx)` | All persons ordered by name |
| `Update(ctx, person)` | Modify name and note |
| `Delete(ctx, id)` | Remove person |
| `UpdateNetBalanceTx(ctx, dbTx, id, delta)` | **Atomic** balance update within DB transaction |

`UpdateNetBalanceTx` uses SQL arithmetic: `net_balance = net_balance + $delta` — same atomic pattern as account balances.

## Service

**File:** `internal/service/person.go`

### RecordLoan (line ~69)

Two-table atomic update:
1. Creates a transaction (loan_out or loan_in) on the account
2. Updates person.net_balance accordingly
3. Updates account.current_balance accordingly
4. All within a single DB transaction

### RecordRepayment (line ~138)

**Auto-detects direction** based on current person.net_balance:
- If positive (they owe you): repayment enters your account (income)
- If negative (you owe them): repayment leaves your account (expense)

### GetDebtSummary (line ~227)

Computes a comprehensive debt summary:
- Loads person + all related transactions (up to 200)
- Iterates transactions to compute: TotalLent, TotalBorrowed, TotalRepaid
- Calculates repayment progress percentage
- **Projected payoff date:** uses linear model (average repayment rate × remaining) with at least 2 repayments required

### DebtSummary Struct (line ~208)

```go
type DebtSummary struct {
    Person          models.Person
    Transactions    []models.Transaction
    TotalLent       float64
    TotalBorrowed   float64
    TotalRepaid     float64
    ProgressPct     float64    // 0-100
    ProjectedPayoff *time.Time // estimated settlement date (nil if can't compute)
}
```

## Handler

**File:** `internal/handler/pages.go`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/people` | GET | `People()` | People list with cards |
| `/people/add` | POST | `PeopleAdd()` | Create person |
| `/people/{id}` | GET | `PersonDetail()` | Detail page with debt summary |
| `/people/{id}/loan` | POST | `PeopleLoan()` | Record a loan |
| `/people/{id}/repay` | POST | `PeopleRepay()` | Record a repayment |
| `/partials/people-summary` | GET | `PeopleSummary()` | Dashboard partial |

### HTMX Pattern

`PeopleAdd`, `PeopleLoan`, and `PeopleRepay` all call `renderPeopleList()` which re-renders the person cards and returns them as an HTMX partial. This updates the list inline without a full page reload.

## Templates

### Pages

| Template | Purpose |
|----------|---------|
| `pages/people.html` | People list with add-person form |
| `pages/person-detail.html` | Debt summary, progress bar, transaction history |

### Partials

| Template | Purpose |
|----------|---------|
| `partials/person-card.html` | Person card with loan/repay forms (hidden toggles) |
| `partials/people-summary.html` | Dashboard summary (owed to me / I owe) |

### Person Card

Each card shows:
- Name, avatar, net balance (color-coded: green = they owe, red = you owe)
- Hidden loan form (loan_out/loan_in toggle, amount, account, note)
- Hidden repay form (amount, account, note)
- JavaScript toggles for showing/hiding forms

### Person Detail

Shows:
- Person header with avatar, name, net balance status
- Summary grid: TotalLent, TotalBorrowed, TotalRepaid
- Payoff progress bar
- Transaction history (color-coded by type)
- Projected payoff date (if calculable)

## Impact on Dashboard & Report Calculations

### What Loans DO Affect

- **Account balances** — loan_out decreases the account, loan_in increases it, repayments adjust accordingly. These changes flow into `NetWorth`, `CashTotal`, `EGPTotal`, `USDTotal`.
- **PeopleOwedToMe / PeopleIOwe** — displayed on the dashboard as a separate summary (not included in NetWorth to avoid double-counting).

### What Loans Do NOT Affect

- **Monthly spending reports** — spending queries filter `WHERE type = 'expense'`. Loan transactions (`loan_out`, `loan_in`, `loan_repayment`) are excluded.
- **Budget tracking** — budget spending also filters `WHERE type = 'expense'`. Lending money does not count toward category budgets.
- **Materialized view** (`mv_monthly_category_totals`) — filters `WHERE category_id IS NOT NULL`. Loan transactions have no category, so they're excluded.
- **DebtTotal** — placeholder field in DashboardData, not yet populated.

### Why PeopleOwedToMe Is Separate from NetWorth

When you lend 1,000 EGP to Alice:
1. Your account balance drops by 1,000 → NetWorth decreases by 1,000
2. Alice's `net_balance` becomes +1,000 → PeopleOwedToMe increases by 1,000

If PeopleOwedToMe were added to NetWorth, the loan would appear balance-neutral. Instead, they're shown separately so you can see both your liquid position (NetWorth) and your receivables (PeopleOwedToMe).

### Summary

| Metric | Affected by Loans? | Reason |
|--------|-------------------|--------|
| NetWorth | Yes | Via account balance changes |
| CashTotal | Yes | Via account balance changes |
| PeopleOwedToMe/IOwe | Yes | Via person.net_balance |
| Monthly Spending | No | Filters `type = 'expense'` only |
| Budget Progress | No | Filters `type = 'expense'` only |
| Spending Velocity | No | Derived from monthly spending |

## Dashboard Integration

Dashboard shows:
- "Owed to me" total (green)
- "I owe" total (red)
- Rendered via `people-summary` partial

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/person.go` | Person struct |
| `internal/repository/person.go` | CRUD, atomic balance update |
| `internal/service/person.go` | RecordLoan, RecordRepayment, GetDebtSummary |
| `internal/handler/pages.go` | People handlers |
| `internal/templates/pages/people.html` | People list page |
| `internal/templates/pages/person-detail.html` | Person detail page |
| `internal/templates/partials/person-card.html` | Person card partial |

## For Newcomers

- **Denormalized net_balance** — cached for performance, updated atomically with transactions. Same pattern as account balances.
- **Auto-detected repayment direction** — the service reads current net_balance to determine if money enters or leaves the account. No need for the user to specify.
- **Payoff projection** — simple linear model. Requires at least 2 repayments to compute. If no repayments yet, returns nil.
- **Two-table atomicity** — RecordLoan/Repayment update both account and person balances in a single DB transaction.

## Logging

**Service events:**

- `person.created` — new person added
- `person.loan_recorded` — loan recorded for a person (type, currency)
- `person.repayment_recorded` — repayment recorded for a person (currency)

**Page views:** `people`, `person-detail`
