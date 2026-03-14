# Transactions

Transactions are the core data entity in ClearMoney. Every financial event — spending, earning, transferring, exchanging currency — is recorded as a transaction with atomic balance updates.

## Transaction Types

| Type | Behavior | BalanceDelta |
|------|----------|-------------|
| `expense` | Debits the account, categorized | `-amount` |
| `income` | Credits the account, categorized | `+amount` |
| `transfer` | Paired debit/credit between own accounts (same currency) | Source: `-amount`, Dest: `+amount` |
| `exchange` | Cross-currency transfer (e.g., USD→EGP) with exchange rate | Source: `-amount`, Dest: `+counterAmount` |
| `loan_out` | Lent money to someone | `-amount` |
| `loan_in` | Borrowed money from someone | `+amount` |
| `loan_repayment` | Partial/full repayment | Direction auto-detected |

## Model

**File:** `internal/models/transaction.go`

Key fields:
- `ID` (UUID), `Type`, `Amount` (always positive), `Currency`
- `AccountID` (primary account), `CounterAccountID` (for transfers/exchanges, nullable)
- `CategoryID` (nullable — transfers don't need categories)
- `Date` (DATE), `Time` (optional), `Note`, `Tags` (PostgreSQL text[] array)
- **Exchange fields:** `ExchangeRate`, `CounterAmount`, `FeeAmount`, `FeeAccountID`
- **Relationship fields:** `PersonID`, `LinkedTransactionID` (self-referencing FK), `RecurringRuleID`
- `BalanceDelta` — signed impact on account balance (critical for reconciliation)

## Entry Methods

### Standard Form

**Route:** `GET /transactions/new` → `POST /transactions`

Full form with amount, account, category, date, note. Category dropdowns show emoji icons grouped by type (Expense/Income optgroups).

### Quick Entry

**Route:** `GET /transactions/quick-form` (HTMX partial) → `POST /transactions/quick`

Bottom sheet with smart features:
- **Smart category suggestion** — as user types a note, the app calls `GET /api/transactions/suggest-category?note=...` which returns the most-used category for similar notes (debounced 300ms, min 3 chars)
- **Smart defaults** — pre-selects last used account and most frequent category

### Batch Entry

**Route:** `GET /batch-entry` → `POST /transactions/batch`

Enter multiple transactions at once. Each row has amount, account, category, date, note.

### Salary Wizard

**Routes:** `GET /salary` → `POST /salary/step2` → `POST /salary/step3` → `POST /salary/confirm`

Multi-step wizard:
1. **Step 1:** Enter salary amount in USD, select source account, date
2. **Step 2:** Enter exchange rate (USD → EGP)
3. **Step 3:** Allocate EGP across destination accounts
4. **Step 4:** Confirm and create all transactions atomically

### Quick Exchange

**Route:** `GET /exchange/quick-form` (HTMX partial)

Exchange tab in the quick-entry bottom sheet for fast currency swaps.

## How Transfers Work

**Service:** `internal/service/transaction.go` — `CreateTransfer()` (line ~147)

Transfers create **two linked transactions** in a single DB transaction:

1. **Debit leg:** Type=transfer, AccountID=source, BalanceDelta=-amount
2. **Credit leg:** Type=transfer, AccountID=dest, BalanceDelta=+amount
3. Bidirectionally linked via `LinkedTransactionID`
4. Both account balances updated atomically

Both legs have the same Amount (positive) and Type. BalanceDelta differs.

## How Exchanges Work

**Service:** `internal/service/transaction.go` — `CreateExchange()` (line ~256)

Exchanges are like transfers but across currencies:

- **Input:** Any 2 of (Amount, Rate, CounterAmount) — 3rd is auto-calculated
- **Rate convention:** User always thinks "EGP per 1 USD" (e.g., 50.5)
- **Rate inversion:** When source=EGP, the service inverts the rate internally before calculation, then inverts back for storage/display

Example: Exchange 100 USD → EGP at rate 50.5:
- Record 1: AccountID=USD_acc, Amount=100, Currency=USD, ExchangeRate=50.5, BalanceDelta=-100
- Record 2: AccountID=EGP_acc, Amount=5050, Currency=EGP, ExchangeRate=50.5, BalanceDelta=+5050

Exchange rates are logged to `exchange_rate_log` table for historical tracking.

## Balance Delta & Reconciliation

Every transaction records its `balance_delta` — the signed impact on the account's balance.

**Reconciliation formula:**
```
expected_balance = initial_balance + SUM(balance_delta)
```

If `expected_balance ≠ current_balance`, a discrepancy is detected. The `make reconcile` command checks this.

## Repository

**File:** `internal/repository/transaction.go` (~644 lines)

### CRUD

| Method | Purpose |
|--------|---------|
| `Create(ctx, tx)` | Insert transaction |
| `CreateTx(ctx, dbTx, tx)` | Create within DB transaction |
| `GetByID(ctx, id)` | Single transaction |
| `Update(ctx, tx)` | Modify transaction |
| `Delete(ctx, id)` | Hard delete |
| `LinkTransactionsTx(ctx, dbTx, id1, id2)` | Bidirectional link for transfers |

### Retrieval

| Method | Purpose |
|--------|---------|
| `GetRecent(ctx, limit)` | Recent transactions across all accounts |
| `GetByAccount(ctx, accountID, limit)` | For a specific account |
| `GetByDateRange(ctx, from, to)` | All in date range (CSV export) |
| `GetByPersonID(ctx, personID, limit)` | Loan/repayment transactions for a person |
| `GetByAccountDateRange(ctx, accountID, from, to)` | For CC statement |
| `GetPaymentsToAccount(ctx, accountID, limit)` | Credits to account (payment history) |
| `GetFiltered(ctx, filter)` | Dynamic WHERE clause filtering |

### Smart Features

| Method | Purpose |
|--------|---------|
| `GetLastUsedAccountID(ctx)` | Most recent expense/income account |
| `GetRecentCategoryIDs(ctx, txType, limit)` | Categories ordered by frequency |
| `GetConsecutiveCategoryID(ctx, txType, count)` | Auto-select if same category used N times in a row |
| `SuggestCategory(ctx, noteKeyword)` | Most common category for matching notes (ILIKE) |
| `HasDepositInRange(ctx, accountID, minAmount, from, to)` | For account health checks |

### TransactionFilter

```go
type TransactionFilter struct {
    AccountID  string
    CategoryID string
    Type       string
    DateFrom   *time.Time
    DateTo     *time.Time
    Search     string    // ILIKE on note (uses pg_trgm index)
    Limit      int
    Offset     int
}
```

## Service

**File:** `internal/service/transaction.go` (~854 lines)

### Key Methods

| Method | Purpose |
|--------|---------|
| `Create(ctx, tx)` | Create single transaction atomically |
| `CreateTransfer(ctx, ...)` | Paired transfer (2 linked records) |
| `CreateExchange(ctx, params)` | Currency exchange with rate calculation |
| `CreateInstapayTransfer(ctx, ...)` | Transfer + auto-calculated InstaPay fee |
| `CreateFawryCashout(ctx, ...)` | CC to prepaid cash-out with fee |
| `Update(ctx, updated)` | Modify + recalculate balance delta |
| `Delete(ctx, id)` | Delete + reverse balance (handles linked txs) |
| `GetSmartDefaults(ctx, txType)` | Last account, frequent categories, auto-select |
| `SuggestCategory(ctx, keyword)` | Category suggestion by note keyword |

### Atomicity Pattern

All write operations use database transactions (`*sql.Tx`):
1. `BeginTx()` starts the transaction
2. All operations use `*Tx` variants (CreateTx, UpdateBalanceTx, etc.)
3. `defer dbTx.Rollback()` for safety
4. `Commit()` at end — if any step fails, everything rolls back

## Handler

### JSON API

**File:** `internal/handler/transaction.go`

| Route | Method | Purpose |
|-------|--------|---------|
| `POST /api/transactions/` | Create | Create transaction, return tx + new balance |
| `POST /api/transactions/transfer` | Transfer | Create transfer |
| `POST /api/transactions/exchange` | Exchange | Create exchange |
| `GET /api/transactions/` | List | List with optional filters |
| `GET /api/transactions/{id}` | Get | Single transaction |
| `DELETE /api/transactions/{id}` | Delete | Delete transaction |

### HTML/HTMX Routes

**File:** `internal/handler/pages.go`

Key routes include transaction CRUD, transfer, exchange, quick-entry, batch-entry, salary wizard, edit/delete inline, category suggestion API, and CSV export.

## Templates

### Pages

| Template | Purpose |
|----------|---------|
| `pages/transaction-new.html` | Full form for single transaction |
| `pages/transactions.html` | Filtered list with search, date range, filters |
| `pages/transfer.html` | Transfer form |
| `pages/exchange.html` | Exchange form |
| `pages/batch-entry.html` | Multiple transaction form |
| `pages/salary.html` | Salary wizard |

### Partials

| Template | Purpose |
|----------|---------|
| `partials/quick-entry.html` | Bottom sheet with smart suggestion |
| `partials/quick-transfer.html` | Transfer in bottom sheet |
| `partials/quick-exchange.html` | Exchange in bottom sheet |
| `partials/transaction-row.html` | Single row with edit/delete buttons |
| `partials/transaction-list.html` | Container with "load more" |
| `partials/transaction-edit-form.html` | Inline edit form |
| `partials/transaction-success.html` | Green success with new balance |
| `partials/transfer-form.html` | Transfer form fields |
| `partials/exchange-form.html` | Exchange form fields |
| `partials/salary-step1.html` through `salary-success.html` | Wizard steps |

## Database

### Migration 000005: Create Transactions

**File:** `internal/database/migrations/000005_create_transactions.up.sql`

Creates the `transactions` table with UUID PK, all fields, foreign keys, and indexes.

### Migration 000012: Add balance_delta

Adds `balance_delta NUMERIC(15,2) NOT NULL DEFAULT 0` column.

### Migration 000013: Performance Indexes & Views

- Composite index: `(account_id, date DESC)` for fast account-filtered sorting
- GIN trigram index on `note` for fast ILIKE search (`pg_trgm` extension)
- Materialized views: `mv_monthly_category_totals`, `mv_daily_tx_counts`

## UX Features

### Swipe-to-Delete

**Frontend:** `static/js/gestures.js` — detects touch drag left >80px, shows red delete indicator, sends DELETE request.

**Backend:** Handler returns empty 200 OK; HTMX removes the row from DOM via `hx-swap="outerHTML"`.

### Category Suggestions

As user types in the note field (quick-entry), the app debounces 300ms, then fetches the most-used category for similar notes. Only auto-selects if category dropdown is empty (preserves user intent).

### Smart Defaults

Pre-selects last used account and most frequent categories. If the same category was used in the last N consecutive transactions, it auto-selects.

## Key Files

| File | Purpose |
|------|---------|
| `internal/models/transaction.go` | Transaction struct, types, constants |
| `internal/repository/transaction.go` | SQL queries, filtering, smart features |
| `internal/service/transaction.go` | Business logic, transfers, exchanges, atomicity |
| `internal/handler/transaction.go` | JSON API |
| `internal/handler/pages.go` | HTML/HTMX handlers |
| `internal/templates/pages/transaction-new.html` | Transaction form |
| `internal/templates/pages/transactions.html` | Transaction list |
| `internal/templates/partials/quick-entry.html` | Quick-entry bottom sheet |
| `internal/database/migrations/000005_create_transactions.up.sql` | Schema |

## For Newcomers

- **Amount is always positive** in the model. Direction is determined by `Type` and `BalanceDelta`.
- **Transfers/exchanges create two records** linked by `LinkedTransactionID`. Deleting one deletes both.
- **DB transactions are critical** — never update balances without wrapping in `*sql.Tx`.
- **Exchange rate convention** — always stored as "EGP per 1 USD" regardless of direction.
- **Tags** exist in the model/DB but are not yet exposed in UI for filtering.
- **Template pitfall** — date inputs must be pre-populated with `value="{{formatDateISO .Today}}"`.
