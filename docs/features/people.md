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

### Person Operations

| Method | Purpose |
|--------|---------|
| `get_all(user_id)` | All people, ordered by name |
| `get_by_id(user_id, person_id)` | Single person |
| `create(user_id, data)` | Create new person with name |
| `update(user_id, person_id, data)` | Update person (e.g., name, avatar) |
| `delete(user_id, person_id)` | Remove person (hard delete) |

### Loan/Repayment Operations

| Method | Purpose |
|--------|---------|
| `record_loan(user_id, person_id, account_id, amount, note)` | Create loan_out or loan_in transaction, update person per-currency balance |
| `record_repayment(user_id, person_id, account_id, amount, note)` | Auto-detect direction, create loan_repayment, update balances |
| `get_debt_summary(user_id, person_id)` | Comprehensive summary with per-currency breakdown, transaction history, projected payoff date |

### DebtSummary

Comprehensive summary returned by `get_debt_summary`:
- `person` — the person record
- `transactions` — list of loan/repayment transactions (up to 200)
- `by_currency` — list of `CurrencyDebt` objects (EGP first then USD), each with:
  - `currency`, `total_lent`, `total_borrowed`, `total_repaid`, `net_balance`, `progress_pct` (0–100)
- `aggregate_totals` — across all currencies: `total_lent`, `total_borrowed`, `total_repaid`, `progress_pct`
- `projected_payoff` — estimated date (requires at least 2 repayments per currency)

## Views

**File:** `backend/people/views.py`

### HTML Routes

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/people` | GET | `people_page()` | People list with cards |
| `/people/add` | POST | `people_add()` | Create person |
| `/people/<id>` | GET | `person_detail()` | Detail page with debt summary |
| `/people/<id>/loan` | POST | `people_loan()` | Record a loan |
| `/people/<id>/repay` | POST | `people_repay()` | Record a repayment |
| `/partials/people-summary` | GET | `people_summary_partial()` | Dashboard partial |

### JSON API Routes

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/api/people` | GET | `people_list()` | List all people (JSON) |
| `/api/people` | POST | `people_create()` | Create person (JSON) |
| `/api/people/<id>` | GET | `person_detail_json()` | Get person with debt summary (JSON) |
| `/api/people/<id>` | PUT | `person_update()` | Update person (JSON) |

### HTMX Pattern

`people_add()`, `people_loan()`, and `people_repay()` all re-render the person cards and return them as an HTMX partial. This updates the list inline without a full page reload.

## Templates

### Pages

| Template | Purpose |
|----------|---------|
| `backend/people/templates/people/people.html` | People list with add-person form |
| `backend/people/templates/people/person-detail.html` | Per-currency debt summary, progress bars, transaction history |

### Partials

| Template | Purpose |
|----------|---------|
| `backend/people/templates/people/partials/person-card.html` | Person card with per-currency balances and loan/repay forms |
| `backend/people/templates/people/partials/people-summary.html` | Dashboard summary with per-currency breakdown |
| `backend/people/templates/people/partials/debt-progress.html` | Contains `debt-progress` (legacy) and `debt-progress-currency` partials |

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
| `backend/people/services.py` | CRUD, atomic balance update, record_loan, record_repayment, get_debt_summary |
| `backend/people/views.py` | People views (HTML and JSON API) |
| `backend/people/templates/people/people.html` | People list page |
| `backend/people/templates/people/person-detail.html` | Person detail page with per-currency stats |
| `backend/people/templates/people/partials/person-card.html` | Person card partial with per-currency balances |
| `backend/people/templates/people/partials/people-summary.html` | Dashboard widget with per-currency breakdown |

## For Newcomers

- **Per-currency balances** — each person has independent EGP and USD balances. The currency is determined by the account used for the loan.
- **Legacy net_balance** — kept for backward compatibility, always equals `net_balance_egp + net_balance_usd`. New code should use the per-currency fields.
- **Auto-detected repayment direction** — the service reads the per-currency balance to determine if money enters or leaves the account. No need for the user to specify.
- **Payoff projection** — simple linear model. Requires at least 2 repayments to compute.
- **Two-table atomicity** — record_loan/record_repayment update both account and person balances in a single DB transaction.

## Logging

**Service events:**

- `person.created` — new person added
- `person.updated` — person details modified
- `person.loan_recorded` — loan recorded for a person (type, currency)
- `person.repayment_recorded` — repayment recorded for a person (currency)

**Page views:** `people`, `person-detail`
