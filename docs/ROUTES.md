# ClearMoney — Complete Route Inventory

> 106+ routes across 13 feature areas. Every endpoint documented with purpose, HTTP method, and use case.

---

## Quick Reference

| Feature Area | Route Count | Endpoints |
|--------------|-------------|-----------|
| Auth & Session | 5 | login, verify, logout, status |
| Dashboard | 4 | home, partials |
| Accounts & Institutions | 25 | CRUD, forms, presets, JSON API |
| Transactions | 24 | CRUD, quick entry, transfers, exchanges, batch, sync |
| Reports | 1 | monthly spending |
| Budgets | 5 | CRUD, total budget |
| People | 8 | CRUD, loan/repay |
| Virtual Accounts | 11 | CRUD, allocate, archive |
| Recurring | 5 | CRUD, confirm, skip |
| Investments | 4 | CRUD |
| Exchange Rates | 1 | rates history |
| Settings | 9 | categories CRUD, export |
| Categories API | 2 | list/create, detail |
| Push Notifications | 3 | vapid, subscribe, check |
| **Total** | **106+** | |

---

## Auth & Session

### POST `/login`
Create or request magic link for login/registration.

**Form fields:**
- `email` (required)
- `website` (honeypot, must be empty)
- Rate limited: 5-min cooldown per email, 3/day per email, 50/day global
- Anti-bot: form submission must take > 2 seconds

**Response:**
- Always shows "check your email" page (never reveals if email exists for login)
- Registration shows "already registered" error if email found

**Related:** `auth_app/services.py:AuthService.request_login_link()`

---

### GET `/auth/verify?token=xxx`
Verify magic link token and create session.

**Query params:**
- `token` (required, 32-char random)

**Process:**
1. Validate token (not used, not expired)
2. Mark token as used (single-use enforcement)
3. Login: look up user by email
4. Registration: create user + seed 25 default categories
5. Create session row (30-day TTL)
6. Set `clearmoney_session` cookie (httponly, samesite=Lax)
7. Redirect to `/`

**Related:** `auth_app/services.py:AuthService.verify_magic_link()`

---

### POST `/logout`
Delete session and clear authentication.

**Process:**
1. Delete session row from DB
2. Clear `clearmoney_session` cookie
3. Redirect to `/login`

---

### GET `/api/session-status`
Check if user's session is still valid (JSON).

**Response:**
```json
{
  "is_authenticated": true,
  "expires_at": "2026-04-25T10:00:00Z",
  "minutes_remaining": 1234
}
```

**Use case:** Client-side timeout warning modal (e.g., "Your session expires in 5 minutes")

---

## Dashboard

### GET `/`
Home page. Aggregates net worth, spending, budgets, CC summary, recent transactions.

**Loads via HTMX partials:**
- Recent transactions (auto-refreshed on transaction create)
- People summary
- Net worth breakdown (by card type)

**Related:** `dashboard/services.py:DashboardService`

---

### GET `/partials/recent-transactions`
Recent transactions list (HTMX partial).

**HTMX swap:** `innerHTML` into `#recent-transactions`

---

### GET `/partials/people-summary`
People ledger summary (HTMX partial).

**HTMX swap:** `innerHTML` into `#people-summary`

---

### GET `/dashboard/net-worth/<card_type>`
Net worth breakdown by account type (HTMX partial for bottom sheet).

**Card types:** `savings`, `checking`, `credit_card`, `virtual`, `investment`, `people`

---

## Accounts & Institutions

### Account Pages

#### GET `/accounts`
List all accounts grouped by institution.

**Includes:**
- Institutions with account cards
- Balance sparklines per account
- Health status indicators
- Dormant toggle
- Add account button → form opens in bottom sheet

---

#### GET `/accounts/<id>`
Account detail page. Shows recent transactions, balance history, utilization (for CC), statement (for CC).

---

#### GET `/accounts/<id>/statement`
Credit card statement view. Shows transactions in statement period, opening/closing balances, interest-free period countdown.

---

### Account Forms

#### GET `/accounts/add-form`
Add account form (HTMX partial, renders in bottom sheet).

**Includes:**
- Institution selector (with option to add new)
- Account type (Savings / Checking / CC / etc.)
- Currency selector
- Initial balance field

---

#### GET `/accounts/form?institution_id=<id>`
Account form with institution pre-selected (HTMX partial).

---

### Account CRUD

#### POST `/accounts/add`
Create new account. Validates institution exists, sets initial balance.

**Fields:**
- `name`, `type`, `currency`, `institution_id`, `initial_balance`

**Response:** HTMX replaces account card or adds new institution card

---

#### POST `/accounts/<id>/edit`
Update account details (name, type, balance).

**Fields:** `name`, `type`, `initial_balance`, `min_balance`, `min_deposit`

**Note:** Currency and type cannot be changed after creation (prevents reconciliation breaks)

---

#### DELETE `/accounts/<id>`
Delete account. Shows confirmation bottom sheet first (requires typing account name).

**Cascades:** Deletes all transactions, snapshots, allocations

---

#### POST `/accounts/<id>/dormant`
Toggle dormant status. Account stays in totals but de-prioritized in UI.

---

#### POST `/accounts/<id>/health`
Update health constraints (min_balance, min_deposit).

**Fields:** `min_balance`, `min_deposit`

---

#### POST `/accounts/reorder`
Reorder accounts within an institution.

**Fields:** `account_ids[]` (ordered list)

---

### Institution Pages

#### GET `/accounts` (main accounts page includes institution cards)

---

### Institution CRUD

#### POST `/institutions/add`
Create new institution. Shows form with name, type selector.

**Institution types:** `bank`, `fintech`, `wallet`, `brokerage`

---

#### GET `/institutions/<id>/edit-form`
Edit institution form (HTMX partial).

---

#### POST `/institutions/<id>/update`
Update institution (name, type, color).

---

#### GET `/institutions/<id>/delete-confirm`
Delete confirmation bottom sheet. Requires typing institution name.

---

#### DELETE `/institutions/<id>`
Delete institution. Cascades to all accounts and transactions.

---

#### POST `/institutions/reorder`
Reorder institutions.

**Fields:** `institution_ids[]` (ordered list)

---

### Institution Presets

#### GET `/accounts/institution-presets?type=bank`
Get preset institutions for a given type (JSON).

**Types:** `bank`, `fintech`, `wallet`

**Response:**
```json
[
  { "id": "cib", "name": "Commercial International Bank", "icon": "cib.png" },
  { "id": "ebank", "name": "EGBank", "icon": "ebank.png" }
]
```

---

### JSON API (Accounts)

#### GET `/api/accounts`
List all accounts (JSON).

**Query params:**
- `institution_id` (optional, filter by institution)

**Response:** Array of account objects with balances, sparklines

---

#### POST `/api/accounts`
Create account (JSON).

---

#### GET `/api/accounts/<id>`
Get single account details (JSON).

---

#### PUT `/api/accounts/<id>`
Update account (JSON).

---

#### DELETE `/api/accounts/<id>`
Delete account (JSON).

---

### JSON API (Institutions)

#### GET `/api/institutions`
List institutions (JSON).

---

#### POST `/api/institutions`
Create institution (JSON).

---

#### GET `/api/institutions/<id>`
Get institution details (JSON).

---

#### PUT `/api/institutions/<id>`
Update institution (JSON).

---

#### DELETE `/api/institutions/<id>`
Delete institution (JSON).

---

## Transactions

### Pages

#### GET `/transactions`
Transactions list page. Supports filtering by account, category, type, date range, search.

**Filters (via query params):**
- `account_id` — filter by account
- `category_id` — filter by category
- `type` — expense, income, transfer, exchange
- `from_date` — start date (YYYY-MM-DD)
- `to_date` — end date (YYYY-MM-DD)
- `search` — search in description

---

#### GET `/transactions/new`
Transaction form page (expense or income).

**Supports:**
- Duplicate from existing: `?dup=<tx_id>` pre-fills form with previous transaction

---

#### GET `/transfer/new`
Unified transfer and exchange form page. Auto-detects mode based on selected account currencies.

---

#### GET `/batch-entry`
Batch entry page. Add multiple transactions in a table format.

---

### Partials

#### GET `/transactions/list`
HTMX partial for filtered transaction list.

---

#### GET `/transactions/quick-form`
Quick entry form (from dashboard bottom sheet).

**Minimal fields:** Amount, Category, Account, Note

---

#### GET `/transactions/quick-transfer-unified`
Unified transfer/exchange form (HTMX partial).

---

#### GET `/transactions/detail/<id>`
Bottom sheet detail view for a single transaction. Shows all fields + edit/delete buttons.

---

#### GET `/transactions/edit/<id>`
Inline edit form for a transaction (HTMX partial).

---

#### GET `/transactions/row/<id>`
Single transaction row HTML (used to cancel edit and show row again).

---

### Create/Update

#### POST `/transactions` (via HTMX form submission)
Create expense or income transaction.

**Fields:**
- `amount`, `category_id`, `account_id`, `date`, `note`, `virtual_account_id` (optional)

**Validation:**
- Amount > 0
- Category type matches transaction type (expense vs income)
- Account exists and belongs to user
- Currency enforced from account (never trust form currency)

**Atomic operations:**
1. Create transaction row
2. Update account balance
3. Allocate to virtual account (if specified)
4. Create balance_delta for reconciliation

**Response:** Toast notification + auto-refresh recent transactions partial

---

#### POST `/transactions/quick`
Create quick-entry transaction. Similar to above but minimal fields, shows toast instead of page refresh.

---

#### PUT `/transactions/<id>`
Update existing transaction (via JSON API or HTMX). Recalculates balance deltas, re-allocates virtual accounts.

---

#### DELETE `/transactions/<id>`
Delete transaction. Reverses balance updates, deallocates from virtual accounts.

---

#### POST `/transactions/transfer`
Create transfer between own accounts.

**Fields:**
- `from_account_id`, `to_account_id`, `amount`, `fee` (optional), `date`, `note`

**Process:**
1. Validate both accounts exist and belong to user
2. Create two transaction rows (one debit, one credit)
3. Update both account balances atomically
4. Link transactions via `linked_transaction_id`

**Note:** Fee is added to the "from" account debit (money out = amount + fee)

---

#### POST `/transactions/exchange-submit`
Create cross-currency exchange (USD↔EGP).

**Fields:**
- `from_account_id` (USD), `to_account_id` (EGP), `amount_from`, `exchange_rate`, `date`, `note`

**Process:**
1. Calculate amount_to using exchange rate
2. Create paired transactions (debit from, credit to)
3. Record exchange rate used for future reference

---

#### POST `/transactions/batch`
Create multiple transactions at once.

**Fields:** Array of transaction objects (each with amount, category, account, etc.)

**Validation:** Each transaction validated individually, all-or-nothing atomicity

---

### API Routes

#### POST `/sync/transactions`
Bulk import transactions (for offline sync from mobile app).

**Purpose:** Allow offline-first mobile clients to sync batches of transactions.

**Fields:** Array of transaction objects

---

#### GET `/api/transactions/suggest-category?description=<text>`
AI-powered category suggestion based on transaction description.

**Response:**
```json
{
  "suggested_category_id": "uuid",
  "suggested_category_name": "Groceries",
  "confidence": 0.92
}
```

**Uses:** Last 50 transactions with matching keywords, category frequency

---

#### POST `/api/transactions/transfer`
JSON API version of transfer creation.

---

#### POST `/api/transactions/exchange`
JSON API version of exchange creation.

---

#### GET `/api/transactions`
List transactions (JSON).

**Query params:** account_id, category_id, type, from_date, to_date, search, limit, offset

---

#### POST `/api/transactions`
Create transaction (JSON).

---

#### GET `/api/transactions/<id>`
Get single transaction (JSON).

---

#### PUT `/api/transactions/<id>`
Update transaction (JSON).

---

#### DELETE `/api/transactions/<id>`
Delete transaction (JSON).

---

## Reports

### GET `/reports`
Monthly spending report page.

**Includes:**
- Month/year selector for navigation
- Currency selector (show EGP or USD breakdown)
- Account filter (all or specific account)
- Spending by category (donut chart, CSS conic-gradient)
- 6-month income vs expense comparison (bar chart)
- Category list with percentages
- Drill-down: click category to see transactions

**Charts:** CSS-only (no Chart.js). See `docs/features/charts.md` for implementation.

---

## Budgets

### GET `/budgets`
Budget management page. Shows category budgets plus the per-currency total
budget card for the user's selected display currency.

**Includes:**
- Add budget form (category + monthly limit + active currency + rollover)
- Copy last month button
- Set/update total budget button
- Warnings if categories exceed total

---

### POST `/budgets/add`
Create per-category budget.

**Fields:** `category_id`, `monthly_limit`, `currency`,
`rollover_enabled`, `max_rollover`

**Validation:** Category required, monthly limit > 0, currency must be active
(blank currency resolves to selected display currency)

---

### POST `/budgets/copy-last-month`
Create missing budgets from last month's expense totals grouped by category and
currency.

---

### GET `/budgets/<id>/`
Budget detail page for one category budget.

Shows current-month matching expense transactions for the same category and
currency.

---

### POST `/budgets/<id>/edit`
Update a category budget's monthly limit and rollover settings.

---

### POST `/budgets/<id>/delete`
Delete per-category budget.

---

### POST `/budgets/total/set`
Create or update the per-currency total monthly budget.

**Fields:** `monthly_limit`, `currency`

**Validation:** limit > 0, currency must be active (blank currency resolves to
selected display currency)

---

### POST `/budgets/total/delete`
Delete total monthly budget.

---

## People

### GET `/people`
People list page. Shows cards for each person with outstanding balance in each currency.

**Includes:**
- Add person form
- List of people with loan/debt amounts
- Indicator: red (you owe), green (they owe)

---

### GET `/people/<id>`
Person detail page. Shows debt summary, loan/repay history, projected payoff date.

**Includes:**
- Per-currency breakdown (EGP, USD, etc.)
- Transaction history (loans and repayments)
- Payoff projection (if paying consistently)

---

### POST `/people/add`
Create person (name + optional note).

**Fields:** `name`, `note` (optional)

**Response:** HTMX adds person card to list

---

### POST `/people/<id>/loan`
Record a loan transaction.

**Direction:** Automatically determined by positive/negative amount:
- Positive amount = you lend to them (money out)
- Negative amount = you borrow from them (money in)

**Fields:** `amount`, `currency`, `date`, `note`

**Process:**
1. Create loan_out or loan_in transaction
2. Update person's balance_<currency> field
3. Create corresponding account transaction (money in/out)

---

### POST `/people/<id>/repay`
Record a repayment.

**Direction:** Automatically determined based on current balance:
- If they owe you: payment reduces their debt
- If you owe them: payment increases their debt (negative)

**Fields:** `amount`, `currency`, `date`, `note`

---

### JSON API (People)

#### GET `/api/persons`
List people (JSON).

---

#### POST `/api/persons`
Create person (JSON).

---

#### GET `/api/persons/<id>`
Get person details (JSON).

---

#### PUT `/api/persons/<id>`
Update person (JSON).

---

#### POST `/api/persons/<id>/loan`
Record loan (JSON).

---

#### POST `/api/persons/<id>/repayment`
Record repayment (JSON).

---

## Virtual Accounts (Envelope Budgeting)

### GET `/virtual-accounts`
Virtual accounts page. Shows all envelopes with progress bars and warnings.

**Includes:**
- Add virtual account form
- List of envelopes with allocation progress
- Over-allocation warnings (red border)
- Archive toggle

---

### GET `/virtual-accounts/<id>`
Virtual account detail page. Shows allocations (transaction + direct) and progress toward goal.

---

### POST `/virtual-accounts/add`
Create virtual account (envelope).

**Fields:** `name`, `target_balance`, `linked_account_id` (optional), `color` (optional)

**Note:** Linked account filters which transactions can be allocated to this envelope

---

### GET `/virtual-accounts/<id>/edit-form`
Edit form partial (HTMX).

---

### POST `/virtual-accounts/<id>/edit`
Update virtual account (name, target, linked account).

---

### POST `/virtual-accounts/<id>/archive`
Soft-delete virtual account (hides from UI, keeps history).

---

### POST `/virtual-accounts/<id>/allocate`
Direct allocation (contribution or withdrawal from envelope).

**Fields:** `amount`, `type` (contribute / withdraw), `date`, `note`

**Process:**
1. Create VirtualAccountAllocation row
2. Recalculate balance
3. Check if new balance exceeds target (warning)

---

### POST `/virtual-accounts/<id>/toggle-exclude`
Toggle "exclude from auto-allocate" for a specific linked account.

**Use case:** Some accounts contribute auto to envelope, others don't.

---

### Legacy Redirects

#### GET `/virtual-funds`
Redirect to `/virtual-accounts` (backward compatibility from old naming).

---

## Recurring

### GET `/recurring`
Recurring rules page. Shows active rules + pending queue (transactions due).

**Includes:**
- Add recurring rule form
- Pending transactions (due today or overdue)
- Active rules with next due date
- Auto-confirm option

---

### POST `/recurring/add`
Create recurring rule.

**Fields:**
- `name`, `amount`, `category_id`, `account_id`, `frequency` (monthly/weekly/daily)
- `start_date`, `end_date` (optional)
- `auto_confirm` (checkbox)

**Process:**
1. Store rule with template_transaction JSON
2. Calculate next_due_date
3. If auto_confirm, schedule job to create transaction

---

### POST `/recurring/<id>/confirm`
Confirm and execute pending rule. Creates transaction, advances next_due_date.

**Process:**
1. Create transaction from template
2. Update account balance
3. Calculate next due date (today + frequency)
4. Response: toast notification

---

### POST `/recurring/<id>/skip`
Skip pending rule without creating transaction. Advances next_due_date.

---

#### DELETE `/recurring/<id>`
Delete recurring rule. Removes from queue.

---

## Investments

### GET `/investments`
Portfolio page. Shows all holdings with unit counts, prices, valuations.

**Includes:**
- Add investment form
- List of holdings with total valuation

---

### POST `/investments/add`
Create investment holding.

**Fields:** `name`, `platform` (Thndr, etc.), `units`, `unit_price`, `currency`

**Note:** Valuation = units × unit_price (computed, never stored)

---

### POST `/investments/<id>/update`
Update unit price (NAV update).

**Fields:** `unit_price`, `date`

---

#### DELETE `/investments/<id>`
Delete investment holding.

---

## Exchange Rates

### GET `/exchange-rates`
Exchange rate history page. Shows historical USD/EGP rates with charts.

---

## Settings

### GET `/settings`
Settings page. Dark mode, CSV export, push notification preferences.

**Includes:**
- Dark mode toggle (saves to localStorage)
- CSV export button (with date range selector)
- Push notification preferences

---

### GET `/settings/categories`
Category management page. Shows default + custom categories with CRUD.

**Includes:**
- List of all categories (system + custom)
- Add custom category form
- Edit icon for each custom category
- Delete icon for each custom category
- Soft-delete archive (categories stay in history, hidden from UI)

---

### POST `/settings/categories/add`
Create custom category.

**Fields:** `name`, `type` (expense / income), `icon` (emoji or icon name)

**Validation:**
- Name must be unique per user
- Type matches category type
- System categories cannot be created via this endpoint

---

### POST `/settings/categories/<id>/update`
Update custom category (name, icon).

**Validation:** Cannot update system categories

---

### POST `/settings/categories/<id>/archive`
Soft-delete category. Hides from UI but keeps transaction history intact.

---

### POST `/settings/categories/<id>/unarchive`
Restore archived category.

---

### GET `/export/transactions?from=<YYYY-MM-DD>&to=<YYYY-MM-DD>`
Download CSV of transactions in date range.

**Format:**
```
Date,Type,Amount,Category,Account,Description
2026-03-25,Expense,150.00,Groceries,EGBank,Weekly shopping
```

**Includes:**
- All transaction types (expense, income, transfer, exchange)
- Transfers shown as paired rows
- Exchanges shown with original and converted amounts

---

## Categories API

### GET `/api/categories`
List all categories (JSON).

**Query params:** `type` (filter by expense / income)

---

### POST `/api/categories`
Create custom category (JSON).

---

### PUT `/api/categories/<id>`
Update category (JSON).

---

#### DELETE `/api/categories/<id>`
Delete category (JSON).

---

## Push Notifications

### GET `/api/push/vapid-key`
Get VAPID public key for browser push subscriptions.

**Response:**
```json
{ "vapid_public_key": "..." }
```

---

### POST `/api/push/subscribe`
Accept push subscription from browser.

**Fields:** `subscription` (browser subscription object)

**Process:**
1. Store subscription endpoint + keys in DB
2. Return 200 (browser saves subscription)

---

### GET `/api/push/check`
Poll for pending notifications (JSON).

**Response:**
```json
[
  {
    "id": "...",
    "title": "Budget alert",
    "body": "Groceries exceeded limit",
    "data": { "type": "budget_alert" }
  }
]
```

**Use case:** Client polls every 30 seconds for new notifications (fallback if push service unavailable)

---

## Summary

- **106+ routes** across 13 apps
- **REST conventions**: GET (read), POST (create/update), PUT (update), DELETE (delete)
- **HTMX partials**: Many routes return HTML fragments instead of full pages
- **JSON APIs**: Parallel `/api/*` routes for programmatic access
- **Anti-patterns avoided**: No query string mutations, no hidden side effects, rate limiting + CSRF protection

See `/backend/clearmoney/urls.py` for the complete URL configuration.
