# People (Loans & Debts)

Track informal lending and borrowing with people. Record loans, borrowings, and repayments with automatic per-currency balance tracking and payoff projections.

## Concept

Each person has per-currency balances (`net_balance_egp` and `net_balance_usd`) that independently track the financial relationship in each currency:

- **Positive balance** = they owe you (you lent more than they repaid)
- **Negative balance** = you owe them (you borrowed more than you repaid)
- **Zero** = settled

A single person can have debts in both EGP and USD simultaneously — e.g., they owe you EGP 5,000 while you owe them $200.

## Model

**File:** `backend/core/models.py`

The `Person` model has `net_balance_egp` and `net_balance_usd` as `NUMERIC(15,2)` columns, plus a legacy `net_balance` (sum of both for backward compat).

`net_balance_egp` and `net_balance_usd` are denormalized caches — updated atomically alongside transactions. The legacy `net_balance` is kept in sync as the sum of both.

## Transaction Types for People

| Type | Direction | Account Effect | Person Effect |
|------|-----------|---------------|---------------|
| `loan_out` | You lend money | Account balance decreases | Per-currency balance increases |
| `loan_in` | You borrow money | Account balance increases | Per-currency balance decreases |
| `loan_repayment` | Someone repays | Auto-detected from per-currency balance | Moves toward zero |

## Service

**File:** `backend/people/services.py`

### RecordLoan

Two-table atomic update:
1. Creates a transaction (loan_out or loan_in) on the account
2. Updates the person's per-currency balance (EGP or USD based on account currency)
3. Updates account.current_balance accordingly
4. All within a single DB transaction

### RecordRepayment

**Auto-detects direction** based on the current **per-currency** balance:
- If positive in that currency (they owe you): repayment enters your account (income)
- If negative in that currency (you owe them): repayment leaves your account (expense)

### GetDebtSummary

Computes a comprehensive debt summary:
- Loads person + all related transactions (up to 200)
- Groups transactions by currency to compute per-currency totals
- Calculates per-currency repayment progress percentage
- **Projected payoff date:** uses linear model (average repayment rate x remaining) with at least 2 repayments required

### CurrencyDebt

Per-currency breakdown returned by `get_debt_summary`: currency, total_lent, total_borrowed, total_repaid, net_balance, progress_pct (0–100).

### DebtSummary

Comprehensive summary returned by `get_debt_summary`: person, transactions list, by_currency (list of CurrencyDebt, EGP first then USD), aggregate totals (total_lent, total_borrowed, total_repaid, progress_pct), and projected_payoff date.

## Views

**File:** `backend/people/views.py`

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/people` | GET | `People()` | People list with cards |
| `/people/add` | POST | `PeopleAdd()` | Create person |
| `/people/{id}` | GET | `PersonDetail()` | Detail page with debt summary |
| `/people/{id}/loan` | POST | `PeopleLoan()` | Record a loan |
| `/people/{id}/repay` | POST | `PeopleRepay()` | Record a repayment |
| `/partials/people-summary` | GET | `PeopleSummary()` | Dashboard partial |

### HTMX Pattern

`people_add`, `people_loan`, and `people_repay` all re-render the person cards and return them as an HTMX partial. This updates the list inline without a full page reload.

## Templates

### Pages

| Template | Purpose |
|----------|---------|
| `pages/people.html` | People list with add-person form |
| `pages/person-detail.html` | Per-currency debt summary, progress bars, transaction history |

### Partials

| Template | Purpose |
|----------|---------|
| `partials/person-card.html` | Person card with per-currency balances and loan/repay forms |
| `partials/people-summary.html` | Dashboard summary with per-currency breakdown |
| `partials/debt-progress.html` | Contains `debt-progress` (legacy) and `debt-progress-currency` partials |

### Person Card

Each card shows:
- Name, avatar, per-currency balances (color-coded: green = they owe, red = you owe)
- "Settled" if both EGP and USD balances are zero
- Hidden loan form (loan_out/loan_in toggle, amount, account, note)
- Hidden repay form (amount, account, note)
- JavaScript toggles for showing/hiding forms

### Person Detail

Shows:
- Person header with avatar, name, per-currency balance status
- Per-currency summary grids: TotalLent, TotalBorrowed, TotalRepaid
- Per-currency payoff progress bars
- Transaction history (color-coded by type, amounts shown in transaction currency)
- Projected payoff date (if calculable)

## Impact on Dashboard & Report Calculations

### What Loans DO Affect

- **Account balances** — loan_out decreases the account, loan_in increases it, repayments adjust accordingly. These changes flow into `NetWorth`, `CashTotal`, `EGPTotal`, `USDTotal`.
- **PeopleByCurrency** — per-currency breakdown shown on the dashboard (EGP and USD separately).

### What Loans Do NOT Affect

- **Monthly spending reports** — spending queries filter `WHERE type = 'expense'`. Loan transactions (`loan_out`, `loan_in`, `loan_repayment`) are excluded.
- **Budget tracking** — budget spending also filters `WHERE type = 'expense'`. Lending money does not count toward category budgets.
- **Materialized view** (`mv_monthly_category_totals`) — filters `WHERE category_id IS NOT NULL`. Loan transactions have no category, so they're excluded.

### Why People Debts Are Separate from NetWorth

When you lend 1,000 EGP to Alice:
1. Your account balance drops by 1,000 → NetWorth decreases by 1,000
2. Alice's `net_balance_egp` becomes +1,000 → PeopleByCurrency EGP OwedToMe increases by 1,000

They're shown separately so you can see both your liquid position (NetWorth) and your receivables (people debts).

### Summary

| Metric | Affected by Loans? | Reason |
|--------|-------------------|--------|
| NetWorth | Yes | Via account balance changes |
| CashTotal | Yes | Via account balance changes |
| PeopleByCurrency | Yes | Via person per-currency balances |
| Monthly Spending | No | Filters `type = 'expense'` only |
| Budget Progress | No | Filters `type = 'expense'` only |
| Spending Velocity | No | Derived from monthly spending |

## Dashboard Integration

Dashboard shows per-currency people summary:
- "Owed to me (EGP)" / "I owe (EGP)" totals
- "Owed to me (USD)" / "I owe (USD)" totals (only if non-zero)
- Rendered via `people-summary` partial
- Uses `PeopleByCurrency []PeopleCurrencySummary` from `DashboardData`

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | Person model with per-currency balance columns |
| `backend/people/services.py` | CRUD, atomic balance update, RecordLoan, RecordRepayment, GetDebtSummary |
| `backend/people/views.py` | People views |
| `backend/templates/pages/people.html` | People list page |
| `backend/templates/pages/person-detail.html` | Person detail page with per-currency stats |
| `backend/templates/partials/person-card.html` | Person card partial with per-currency balances |
| `backend/templates/partials/people-summary.html` | Dashboard widget with per-currency breakdown |

## For Newcomers

- **Per-currency balances** — each person has independent EGP and USD balances. The currency is determined by the account used for the loan.
- **Legacy net_balance** — kept for backward compatibility, always equals `net_balance_egp + net_balance_usd`. New code should use the per-currency fields.
- **Auto-detected repayment direction** — the service reads the per-currency balance to determine if money enters or leaves the account. No need for the user to specify.
- **Payoff projection** — simple linear model. Requires at least 2 repayments to compute.
- **Two-table atomicity** — RecordLoan/Repayment update both account and person balances in a single DB transaction.

## Logging

**Service events:**

- `person.created` — new person added
- `person.loan_recorded` — loan recorded for a person (type, currency)
- `person.repayment_recorded` — repayment recorded for a person (currency)

**Page views:** `people`, `person-detail`
