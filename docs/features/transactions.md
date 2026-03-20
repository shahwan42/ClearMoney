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

**File:** `backend/core/models.py`

Key fields:
- `id` (UUID), `type`, `amount` (always positive), `currency`
- `account_id` (FK — primary account), `counter_account_id` (FK, nullable — for transfers/exchanges)
- `category_id` (FK, nullable — transfers don't need categories)
- `date` (DATE), `time` (optional), `note`, `tags` (PostgreSQL text[] array)
- **Exchange fields:** `exchange_rate`, `counter_amount`, `fee_amount`, `fee_account_id`
- **Relationship fields:** `person_id`, `linked_transaction_id` (self-referencing FK), `recurring_rule_id`
- `balance_delta` — signed impact on account balance (critical for reconciliation)

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

**Service:** `backend/transactions/services/` — `create_transfer()`

Transfers create **two linked transactions** in a single DB transaction:

1. **Debit leg:** type=transfer, account_id=source, balance_delta=-amount
2. **Credit leg:** type=transfer, account_id=dest, balance_delta=+amount
3. Bidirectionally linked via `linked_transaction_id`
4. Both account balances updated atomically

Both legs have the same amount (positive) and type. balance_delta differs.

## How Exchanges Work

**Service:** `backend/transactions/services/` — `create_exchange()`

Exchanges are like transfers but across currencies:

- **Input:** Any 2 of (amount, rate, counter_amount) — 3rd is auto-calculated
- **Rate convention:** User always thinks "EGP per 1 USD" (e.g., 50.5)
- **Rate inversion:** When source=EGP, the service inverts the rate internally before calculation, then inverts back for storage/display

Example: Exchange 100 USD → EGP at rate 50.5:

- Record 1: account_id=USD_acc, amount=100, currency=USD, exchange_rate=50.5, balance_delta=-100
- Record 2: account_id=EGP_acc, amount=5050, currency=EGP, exchange_rate=50.5, balance_delta=+5050

Exchange rates are logged to `exchange_rate_log` table for historical tracking.

## Balance Delta & Reconciliation

Every transaction records its `balance_delta` — the signed impact on the account's balance.

**Reconciliation formula:**
```
expected_balance = initial_balance + SUM(balance_delta)
```

If `expected_balance ≠ current_balance`, a discrepancy is detected. The `make reconcile` command checks this.

## Service

**File:** `backend/transactions/services/`

### Key Methods

| Method | Purpose |
|--------|---------|
| `create(tx)` | Create single transaction atomically |
| `create_transfer(...)` | Paired transfer (2 linked records) |
| `create_exchange(params)` | Currency exchange with rate calculation |
| `create_instapay_transfer(...)` | Transfer + auto-calculated InstaPay fee |
| `create_fawry_cashout(...)` | CC to prepaid cash-out with fee |
| `update(updated)` | Modify + recalculate balance delta |
| `delete(id)` | Delete + reverse balance (handles linked txs) |
| `get_smart_defaults(tx_type)` | Last account, frequent categories, auto-select |
| `suggest_category(keyword)` | Category suggestion by note keyword |

### Atomicity Pattern

All write operations use `django.db.transaction.atomic()`:

1. All operations run inside the atomic block
2. If any step raises an exception, everything rolls back automatically

## Views

**File:** `backend/transactions/views.py`

Key routes include transaction CRUD, transfer, exchange, quick-entry, batch-entry, salary wizard, edit/delete inline, category suggestion API, and CSV export.

## Templates

### Pages

| Template | Purpose |
|----------|---------|
| `backend/transactions/templates/transactions/transaction_new.html` | Full form for single transaction |
| `backend/transactions/templates/transactions/transactions.html` | Filtered list with search, date range, filters |
| `backend/transactions/templates/transactions/transfer.html` | Transfer form |
| `backend/transactions/templates/transactions/exchange.html` | Exchange form |
| `backend/transactions/templates/transactions/batch_entry.html` | Multiple transaction form |

### Partials

| Template | Purpose |
|----------|---------|
| `backend/transactions/templates/transactions/_quick_entry.html` | Bottom sheet with smart suggestion |
| `backend/transactions/templates/transactions/_quick_transfer.html` | Transfer in bottom sheet |
| `backend/transactions/templates/transactions/_quick_exchange.html` | Exchange in bottom sheet |
| `backend/transactions/templates/transactions/_transaction_row.html` | Single row with edit/delete buttons |
| `backend/transactions/templates/transactions/_transaction_list.html` | Container with "load more" |
| `backend/transactions/templates/transactions/_transaction_edit_form.html` | Inline edit form |
| `backend/transactions/templates/transactions/_transaction_success.html` | Green success with new balance |

## Database

- **Migration 000005:** Creates `transactions` table with UUID PK, all fields, foreign keys, and indexes.
- **Migration 000012:** Adds `balance_delta NUMERIC(15,2) NOT NULL DEFAULT 0` column.
- **Migration 000013:** Adds composite index `(account_id, date DESC)` + GIN trigram index on `note` for fast ILIKE search + materialized views.

## Account Name & Running Balance

Transaction rows display the **account name** and **running balance** (account balance after each transaction).

**Running balance computation:** Uses a SQL window function (`SUM(balance_delta) OVER (...)`) to compute the true account balance at each point in time. The computation runs over ALL transactions for the account inside a subquery, then filters are applied on the outer query — so the balance is always accurate regardless of active filters.

## UX Features

### Swipe-to-Delete

**Frontend:** `static/js/gestures.js` — detects touch drag left >80px, shows red delete indicator, sends DELETE request.

**Backend:** View returns empty 200 OK; HTMX removes the row from DOM via `hx-swap="outerHTML"`.

### Category Suggestions

As user types in the note field (quick-entry), the app debounces 300ms, then fetches the most-used category for similar notes. Only auto-selects if category dropdown is empty (preserves user intent).

### Smart Defaults

Pre-selects last used account and most frequent categories. If the same category was used in the last N consecutive transactions, it auto-selects.

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | Transaction model, types, constants |
| `backend/transactions/services/` | Business logic, transfers, exchanges, atomicity |
| `backend/transactions/views.py` | HTML/HTMX views |
| `backend/transactions/templates/transactions/transaction_new.html` | Transaction form |
| `backend/transactions/templates/transactions/transactions.html` | Transaction list |
| `backend/transactions/templates/transactions/_quick_entry.html` | Quick-entry bottom sheet |

## Currency Enforcement

The service layer (`create` and `update`) always overrides the transaction's currency with the account's actual currency. This prevents mismatches when the frontend sends an incorrect value (e.g., hidden form field defaulting to EGP for a USD account).

**Pattern:** Views can pass any currency value — the service will look up the account and use its currency as the source of truth.

## For Newcomers

- **Amount is always positive** in the model. Direction is determined by `type` and `balance_delta`.
- **Currency comes from the account** — the service layer enforces this. Don't rely on form fields for currency.
- **Transfers/exchanges create two records** linked by `linked_transaction_id`. Deleting one deletes both.
- **DB transactions are critical** — never update balances without wrapping in `django.db.transaction.atomic()`.
- **Exchange rate convention** — always stored as "EGP per 1 USD" regardless of direction.
- **Tags** exist in the model/DB but are not yet exposed in UI for filtering.

## Logging

**Service events:**

- `transaction.created` — new transaction created (type, currency, account_id)
- `transaction.updated` — transaction modified (id)
- `transaction.deleted` — transaction removed (id)
- `transaction.transfer_created` — paired transfer between accounts (source, dest)
- `transaction.exchange_created` — cross-currency exchange (source, dest)
- `transaction.instapay_created` — InstaPay transfer with auto-calculated fee
- `transaction.fawry_cashout_created` — credit card to prepaid cash-out with fee

**Page views:** `transactions`, `transaction-new`, `transfer-new`, `exchange-new`, `batch-entry`, `fawry-cashout`
