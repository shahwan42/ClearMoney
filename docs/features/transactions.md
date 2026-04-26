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

### Quick Exchange

**Route:** `GET /exchange/quick-form` (HTMX partial)

Exchange tab in the quick-entry bottom sheet for fast currency swaps.

## How Transfers Work

**Service:** `backend/transactions/services/transfers.py` — `create_transfer()`

Transfers create **two linked transactions** in a single DB transaction:

1. **Debit leg:** type=transfer, account_id=source, balance_delta=-amount
2. **Credit leg:** type=transfer, account_id=dest, balance_delta=+amount
3. Bidirectionally linked via `linked_transaction_id`
4. Both account balances updated atomically

Both legs have the same amount (positive) and type. balance_delta differs.

## How Exchanges Work

**Service:** `backend/transactions/services/transfers.py` — `create_exchange()`

Exchanges are like transfers but across currencies:

- **Input:** Any 2 of (amount, rate, counter_amount) — 3rd is auto-calculated
- **Rate convention:** User always thinks "EGP per 1 USD" (e.g., 50.5)
- **Rate inversion:** When source=EGP, the service inverts the rate internally before calculation

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

If `expected_balance ≠ current_balance`, a discrepancy is detected.

## Service Architecture

**File:** `backend/transactions/services/`

The TransactionService is composed from a base class and modular mixins for separation of concerns:

### Service Structure

```
TransactionService
├── TransactionServiceBase (crud.py)
│   ├── __init__, private helpers
│   ├── CRUD: create, update, delete
│   ├── Query: get_by_id, get_by_id_enriched, get_filtered_enriched
│   └── Dropdowns: get_accounts, get_categories, get_virtual_accounts
├── TransferMixin (transfers.py)
│   ├── create_transfer() — same-currency transfer with optional fee
│   ├── create_exchange() — cross-currency exchange
│   └── Helper utilities for rate calculations
└── HelperMixin (helpers.py)
    ├── batch_create() — bulk transaction creation
    ├── get_smart_defaults() — last account, frequent categories
    ├── suggest_category() — keyword-based category suggestion
    ├── Virtual account allocation
    │   ├── allocate_to_virtual_account()
    │   ├── deallocate_from_virtual_accounts()
    │   └── get_allocation_for_tx()
    └── Dropdown queries
```

### Key Methods

| Method | Purpose |
|--------|---------|
| `create(tx)` | Create single transaction atomically |
| `create_transfer(...)` | Paired transfer (2 linked records) with optional fee |
| `create_exchange(params)` | Currency exchange with rate calculation |
| `update(updated)` | Modify + recalculate balance delta |
| `delete(id)` | Delete + reverse balance (handles linked txs) |
| `batch_create(items)` | Create multiple transactions; returns (created, failed) |
| `get_by_id(id)` | Fetch transaction by UUID |
| `get_by_id_enriched(id)` | Fetch with account/category names |
| `get_filtered_enriched(filters)` | Query with search, date range, account/category filters |
| `get_smart_defaults(tx_type)` | Last account, frequent categories, auto-select |
| `suggest_category(keyword)` | Category suggestion by note keyword |
| `allocate_to_virtual_account(tx_id, va_id, amount)` | Allocate transaction to virtual account envelope |
| `deallocate_from_virtual_accounts(tx_id)` | Remove virtual account allocation |
| `get_allocation_for_tx(tx_id)` | Fetch virtual account ID for transaction |

### Atomicity Pattern

All write operations use `django.db.transaction.atomic()`:

1. All operations run inside the atomic block
2. If any step raises an exception, everything rolls back automatically

## Views

**File:** `backend/transactions/views.py`

### Page Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/transactions` | GET, POST | Full transaction list; POST creates expense/income |
| `/transactions/new` | GET | Full transaction form page |
| `/transactions/quick-form` | GET | Quick-entry bottom sheet (HTMX partial) |
| `/transactions/quick` | POST | Create quick-entry transaction |
| `/transactions/quick-transfer-unified` | GET | Unified transfer tab in quick-entry (HTMX partial) |
| `/transactions/transfer` | POST | Create transfer with optional fee |
| `/transactions/exchange-submit` | POST | Create currency exchange |
| `/transactions/batch` | POST | Create multiple transactions |
| `/batch-entry` | GET | Batch entry form page |
| `/transfer/new` | GET | Unified transfer/exchange form page |
| `/exchange/quick-form` | GET | Exchange tab in quick-entry (HTMX partial) |

### Detail Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/transactions/detail/<id>` | GET | Transaction detail bottom sheet (HTMX partial) |
| `/transactions/edit/<id>` | GET | Inline edit form (HTMX partial) |
| `/transactions/row/<id>` | GET | Single transaction row (HTMX partial) |
| `/transactions/<id>` | PUT, DELETE | Update or delete transaction (JSON API) |

### API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/transactions/suggest-category` | GET | Category suggestion by note keyword |
| `/api/transactions` | GET, POST | List or create transactions (JSON API) |
| `/api/transactions/<id>` | GET, PUT, DELETE | Fetch, update, or delete (JSON API) |
| `/api/transactions/transfer` | POST | Create transfer (JSON API) |
| `/api/transactions/exchange` | POST | Create exchange (JSON API) |

### Deprecated/Unified Routes

The following routes have been unified into `/transfer/new`:
- `POST /transactions/instapay-transfer` — redirects to `/transfer/new`
- `GET /transfers/new` — redirects to `/transfer/new`
- `GET /exchange/new` — redirects to `/transfer/new`

InstaPay is now handled as a transfer with optional fees via the unified `create_transfer()` method.

## Templates

### Pages

| Template | Purpose |
|----------|---------|
| `backend/transactions/templates/transactions/transaction_new.html` | Full form for single transaction |
| `backend/transactions/templates/transactions/transactions.html` | Filtered list with search, date range, filters |
| `backend/transactions/templates/transactions/transfer_unified.html` | Unified transfer/exchange form |
| `backend/transactions/templates/transactions/batch_entry.html` | Multiple transaction form |

### Partials

| Template | Purpose |
|----------|---------|
| `backend/transactions/templates/transactions/_quick_entry.html` | Bottom sheet with smart suggestion |
| `backend/transactions/templates/transactions/_quick_transfer_unified.html` | Unified transfer in bottom sheet |
| `backend/transactions/templates/transactions/_transfer_unified_form.html` | Unified transfer form (partial) |
| `backend/transactions/templates/transactions/_transaction_row.html` | Single row with edit/delete buttons |
| `backend/transactions/templates/transactions/_transaction_list.html` | Container with "load more" |
| `backend/transactions/templates/transactions/_transaction_edit_form.html` | Inline edit form |
| `backend/transactions/templates/transactions/_transaction_detail_sheet.html` | Detail bottom sheet |
| `backend/transactions/templates/transactions/_transaction_success.html` | Green success with new balance |

## Virtual Account Allocation

Transactions can be allocated to virtual accounts (envelopes) for budget tracking. The service provides three methods:

- `allocate_to_virtual_account(tx_id, va_id, amount)` — Allocate transaction to a virtual account envelope. Amount is signed (negative for expenses).
- `deallocate_from_virtual_accounts(tx_id)` — Remove virtual account allocation, typically when transaction is deleted or reallocated.
- `get_allocation_for_tx(tx_id)` — Fetch the virtual account ID allocated to a transaction (returns None if unallocated).

## UX Features

### Delete Transactions

Transaction rows expose deletion through the explicit row menu. The delete action uses `hx-delete` with the app-native confirmation dialog, then removes the row from the DOM via `hx-swap="outerHTML"`.

### Category Suggestions

As user types in the note field (quick-entry), the app debounces 300ms, then fetches the most-used category for similar notes. Only auto-selects if category dropdown is empty (preserves user intent).

### Smart Defaults

Pre-selects last used account and most frequent categories. If the same category was used in the last N consecutive transactions, it auto-selects.

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/models.py` | Transaction model, types, constants |
| `backend/transactions/services/crud.py` | CRUD operations, queries, enrichment |
| `backend/transactions/services/transfers.py` | Transfer, exchange business logic |
| `backend/transactions/services/helpers.py` | Batch create, smart defaults, VA allocation |
| `backend/transactions/services/utils.py` | Utilities, fee calculations, validations |
| `backend/transactions/views.py` | HTTP views, HTMX handlers |
| `backend/transactions/urls.py` | Route configuration |
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
- **Service composition** — TransactionService uses mixins for modularity. Check `services/__init__.py` to understand the composition pattern.
- **Virtual accounts** — transactions can be allocated to budgets (envelopes) for tracking. Use the VA allocation methods when creating/updating transactions.

## Logging

**Service events:**

- `transaction.created` — new transaction created (type, currency, account_id)
- `transaction.updated` — transaction modified (id)
- `transaction.deleted` — transaction removed (id)
- `transaction.transfer_created` — paired transfer between accounts (source, dest)
- `transaction.exchange_created` — cross-currency exchange (source, dest)

**Page views:** `transactions`, `transaction-new`, `transfer-new`, `exchange-new`, `batch-entry`
