# ClearMoney — Backend Architecture

> Complete Django backend with 14 Django apps, 125+ routes, 1129+ tests. Service-oriented architecture with atomic transactions and per-user data isolation.

---

## Quick Start

**Directory structure:**
```
backend/
  clearmoney/           # Django settings, URLs, WSGI
  core/                 # Models, auth, template tags, types
  auth_app/             # Magic link authentication
  dashboard/            # Home page aggregation
  accounts/             # Accounts & institutions
  transactions/         # Transactions, transfers, exchanges
  reports/              # Monthly spending reports
  budgets/              # Budget management
  people/               # Loan & debt tracking
  virtual_accounts/     # Envelope budgeting
  recurring/            # Recurring transactions
  investments/          # Investment portfolio
  categories/           # Category JSON API
  exchange_rates/       # Exchange rate reference
  push/                 # Web push notifications
  jobs/                 # Background management commands
  settings_app/         # Settings & CSV export
  tests/                # Shared test fixtures
  templates/            # Base HTML, header, footer
  static/               # CSS, JS, service worker
```

**Key files:**
- `backend/pyproject.toml` — Python dependencies, pytest config, mypy config, coverage
- `backend/clearmoney/urls.py` — Main URL routing
- `backend/core/models.py` — All 18 Django models
- `backend/core/types.py` — `AuthenticatedRequest` type
- `backend/core/templatetags/money.py` — Template filters (currency, charts, etc.)

---

## Core Models (All in `backend/core/models.py`)

### Authentication & Users

#### `User`
No password field — authentication via magic link only.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `email` | VARCHAR(255) | Unique index on `LOWER(email)` for case-insensitive lookup |
| `name` | VARCHAR(255) | Optional display name |
| `created_at` | TIMESTAMP | Account creation date |
| `updated_at` | TIMESTAMP | Last profile update |

**Relations:**
- 1:N with Account
- 1:N with Transaction
- 1:N with Person
- 1:N with RecurringRule
- 1:N with Budget
- 1:N with TotalBudget
- 1:N with Session

---

#### `Session`
Server-side session storage (replaces Django default).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `user_id` | UUID | FK to User |
| `token` | VARCHAR(44) | 32-byte base64-encoded random (from `secrets.token_urlsafe`) |
| `created_at` | TIMESTAMP | Session creation |
| `expires_at` | TIMESTAMP | TTL 30 days |

**Usage:**
1. On `/auth/verify?token=xxx`, creates session row
2. On each request, `GoSessionAuthMiddleware` reads `clearmoney_session` cookie
3. Validates token against DB (not in-memory)
4. Sets `request.user_id` and `request.user_email` on `AuthenticatedRequest`

---

#### `AuthToken`
Temporary magic link tokens (short-lived, single-use).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `email` | VARCHAR(255) | Email requesting link |
| `token` | VARCHAR(44) | 32-byte base64-encoded random |
| `used` | BOOLEAN | Single-use enforcement |
| `created_at` | TIMESTAMP | Token generation time |
| `expires_at` | TIMESTAMP | TTL 15 minutes |

**Anti-patterns:**
- Token reuse detection: if valid unexpired token exists for email, return REUSED (don't send email)
- Rate limits: 5-min cooldown, 3/day per email, 50/day global (via `django-ratelimit`)

---

### Financial Data

#### `Institution`
Banks, fintechs, wallets, brokerages. Grouping container for accounts.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `name` | VARCHAR(255) | "HSBC", "Telda", "Fawry", etc. |
| `type` | ENUM | bank, fintech, wallet, brokerage |
| `color` | VARCHAR(6) | Optional hex color for UI |
| `display_order` | INT | Drag-to-reorder sequence |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**Constraints:**
- `UNIQUE(user_id, name)` — cannot have duplicate institution names per user
- `UNIQUE(user_id, type, display_order)` — enforces ordering sequence

---

#### `Account`
Bank accounts, credit cards, wallets, virtual funds.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `institution_id` | UUID | FK to Institution |
| `name` | VARCHAR(255) | "Personal Savings", "HSBC Visa", etc. |
| `type` | ENUM | savings, checking, cc, credit_limit, prepaid |
| `currency` | ENUM | EGP, USD (fixed after creation) |
| `current_balance` | NUMERIC(15,2) | Cached, updated atomically per transaction |
| `initial_balance` | NUMERIC(15,2) | Starting balance for reconciliation |
| `is_dormant` | BOOLEAN | Hide inactive accounts from UI |
| `display_order` | INT | Drag-to-reorder within institution |
| `health` | JSONB | `{min_balance: 500, min_deposit: 0}` |
| `cc_billing_cycle` | JSONB | For CC accounts: `{statement_date: 10, due_date: 20, credit_limit: 50000}` |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**CC-specific fields** (only for type=cc):
- `cc_billing_cycle.statement_date` — when statement generates (1-28)
- `cc_billing_cycle.due_date` — payment due date (1-31)
- `cc_billing_cycle.credit_limit` — max available credit

**Note on balance:**
- Credit card balance stored as **negative** (represents debt)
- Display with `neg` filter to show as positive "amount used"
- Balance = -(amount spent), increases (more negative) on purchase, decreases (less negative) on payment

**Constraints:**
- `UNIQUE(user_id, name)` — no duplicate account names
- Currency immutable after creation (prevents reconciliation breaks)

---

#### `Category`
Expense and income categories.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User (NULL for system categories) |
| `name` | VARCHAR(100) | "Groceries", "Salary", etc. |
| `type` | ENUM | expense, income |
| `icon` | VARCHAR(50) | Emoji or icon name |
| `is_system` | BOOLEAN | Cannot edit/delete system categories |
| `is_archived` | BOOLEAN | Soft-delete (hidden from UI) |
| `created_at` | TIMESTAMP | |

**System categories:** Global, shared by all users (Salary, Groceries, etc.). Custom categories are per-user.

**Constraints:**
- `UNIQUE(user_id, name, type)` — user cannot have duplicate category names per type

---

#### `Transaction`
Central record for all money movements (expenses, income, transfers, exchanges).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `account_id` | UUID | FK to Account (money flows from/to) |
| `type` | ENUM | expense, income, transfer, exchange |
| `amount` | NUMERIC(15,2) | Always positive; sign determined by type |
| `currency` | ENUM | Enforced from account (never trust form) |
| `category_id` | UUID | FK to Category (NULL for transfers/exchanges) |
| `description` | TEXT | User-entered note |
| `date` | DATE | Transaction date (can be backdated) |
| `is_reconciled` | BOOLEAN | User marked as confirmed (vs. bank match) |
| `linked_transaction_id` | UUID | For transfers: paired debit/credit transaction |
| `exchange_rate` | NUMERIC(10,6) | For exchanges: rate used (USD/EGP) |
| `balance_delta` | NUMERIC(15,2) | Signed: account balance change (+income, -expense) |
| `fee` | NUMERIC(15,2) | For transfers: optional fee (added to amount out) |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**Balance delta tracking:**
- Used for reconciliation: sum of balance_deltas should equal `current_balance - initial_balance`
- Expense: balance_delta = -amount
- Income: balance_delta = +amount
- Transfer: debit tx has delta = -amount, credit tx has delta = +amount

**Constraints:**
- `UNIQUE(id, account_id)` ensures data integrity on concurrent updates
- Transfers: linked_transaction_id creates implicit 1:2 relationship

---

#### `Person`
Track loans, debts, and repayments with individuals.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `name` | VARCHAR(255) | "Ali", "Fatma", etc. |
| `note` | TEXT | Optional description |
| `balance_egp` | NUMERIC(15,2) | Owed/loaned in EGP (positive = they owe you, negative = you owe them) |
| `balance_usd` | NUMERIC(15,2) | Owed/loaned in USD |
| `balance_<other>` | NUMERIC(15,2) | Other currencies |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**Process for loan recording:**
1. Record loan via `POST /people/<id>/loan` with positive/negative amount
2. Creates loan_out or loan_in transaction
3. Creates matching account transaction (money in/out)
4. Updates person's balance_<currency>

---

### Budgeting & Allocation

#### `Budget`
Per-category monthly spending limits.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `category_id` | UUID | FK to Category |
| `amount` | NUMERIC(15,2) | Monthly limit |
| `month` | DATE | First day of month (YYYY-MM-01) |
| `currency` | ENUM | EGP or USD |
| `created_at` | TIMESTAMP | |

**Status calculation:**
- Green: spending < 80% of limit
- Amber: 80–99% of limit
- Red: >= 100% of limit

**Constraints:**
- `UNIQUE(user_id, category_id, month, currency)` — one budget per category per month

---

#### `TotalBudget`
Overall monthly spending cap (sum of all categories).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `amount` | NUMERIC(15,2) | Total limit |
| `month` | DATE | First day of month (YYYY-MM-01) |
| `currency` | ENUM | EGP or USD |
| `created_at` | TIMESTAMP | |

**Constraints:**
- `UNIQUE(user_id, month, currency)` — one total budget per month per currency

---

#### `VirtualAccount`
Envelope budgeting. Separate "buckets" for goals, savings, allocations.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `name` | VARCHAR(255) | "Emergency Fund", "Vacation", etc. |
| `target_balance` | NUMERIC(15,2) | Goal amount |
| `current_balance` | NUMERIC(15,2) | Cached balance from allocations |
| `linked_account_id` | UUID | FK to Account (optional, filter source) |
| `exclude_from_net_worth` | BOOLEAN | Hide from net worth calculation |
| `is_archived` | BOOLEAN | Soft-delete |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**Balance calculation:**
```
current_balance = SUM(allocations.amount) WHERE virtual_account_id = this AND amount_type IN (transaction, direct)
```

---

#### `VirtualAccountAllocation`
Pivot linking transactions or direct allocations to virtual accounts.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `virtual_account_id` | UUID | FK to VirtualAccount |
| `transaction_id` | UUID | FK to Transaction (NULL for direct allocation) |
| `amount` | NUMERIC(15,2) | Amount allocated |
| `allocation_type` | ENUM | transaction, direct_contribution, direct_withdrawal |
| `date` | DATE | Allocation date |
| `note` | TEXT | Optional reason |
| `created_at` | TIMESTAMP | |

**Two types of allocations:**
1. **Transaction allocation**: User tags a transaction as contributing to a VA
2. **Direct allocation**: Manual contribution/withdrawal (no transaction)

---

### Recurring & Automation

#### `RecurringRule`
Scheduled recurring transactions (monthly/weekly/daily).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `name` | VARCHAR(255) | "Rent", "Subscription", etc. |
| `frequency` | ENUM | daily, weekly, monthly, yearly |
| `amount` | NUMERIC(15,2) | Transaction amount |
| `category_id` | UUID | FK to Category |
| `account_id` | UUID | FK to Account |
| `template_transaction` | JSONB | Full transaction data as JSON |
| `next_due_date` | DATE | When rule is next due |
| `last_executed_at` | TIMESTAMP | When last transaction created |
| `auto_confirm` | BOOLEAN | Automatically create transaction (vs. pending queue) |
| `start_date` | DATE | When rule begins |
| `end_date` | DATE | When rule stops (NULL = ongoing) |
| `is_active` | BOOLEAN | Can be disabled without deleting |
| `created_at` | TIMESTAMP | |

**Pending queue:**
- Transactions with `next_due_date <= today` appear in `/recurring` as "confirm" or "skip"
- On confirm: create transaction, advance `next_due_date`
- On skip: advance `next_due_date` (no transaction)

---

### Investments & Snapshots

#### `Investment`
Fund holdings on platforms (Thndr, etc.).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `name` | VARCHAR(255) | Fund name |
| `platform` | VARCHAR(100) | "Thndr", "EFG", etc. |
| `units` | NUMERIC(20,6) | Number of units held |
| `unit_price` | NUMERIC(15,6) | Latest NAV per unit |
| `currency` | ENUM | EGP or USD |
| `purchase_date` | DATE | When acquired |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**Valuation (computed, not stored):**
```
valuation = units × unit_price
portfolio_total = SUM(valuations) for all investments
```

---

#### `DailySnapshot`
Daily financial state for sparklines (net worth, income, expense).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `date` | DATE | Snapshot date |
| `net_worth` | NUMERIC(15,2) | Total net worth at EOD |
| `income` | NUMERIC(15,2) | Income transactions that day |
| `expense` | NUMERIC(15,2) | Expense transactions that day |
| `currency` | ENUM | Base currency |
| `created_at` | TIMESTAMP | |

**Purpose:**
- 30-day sparklines on dashboard
- Tracks daily net worth trend
- Used for spending velocity calculation

---

#### `AccountSnapshot`
Per-account daily balance history.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `user_id` | UUID | FK to User |
| `account_id` | UUID | FK to Account |
| `date` | DATE | Snapshot date |
| `balance` | NUMERIC(15,2) | Account balance at EOD |
| `created_at` | TIMESTAMP | |

**Purpose:**
- 30-day balance sparklines per account
- Utilization trend charts for credit cards

---

### Reference Data

#### `ExchangeRateLog`
Historical USD/EGP exchange rates (global, not user-scoped).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `date` | DATE | Rate date |
| `usd_to_egp` | NUMERIC(10,6) | Exchange rate (1 USD = X EGP) |
| `source` | VARCHAR(100) | Data source (CBE, NBE, etc.) |
| `created_at` | TIMESTAMP | |

**Note:** No user_id — shared across all users. Rates are global reference data.

---

## Django Apps

### 1. **`core`** — Models, Auth Middleware, Template Tags

**Key files:**
- `models.py` — All 14 models (User, Session, Account, Transaction, etc.)
- `middleware.py` — `GoSessionAuthMiddleware` (handles `clearmoney_session` cookie validation)
- `types.py` — `AuthenticatedRequest` (extended HttpRequest with user_id, user_email)
- `managers.py` — `UserScopedManager` (base manager with `.for_user(user_id)` filtering)
- `templatetags/money.py` — Template filters:
  - `format_egp`, `format_usd`, `format_currency` — locale-aware formatting
  - `neg` — negate value (for CC balances: convert -500 to "+500 used")
  - `percentage` — convert 0.45 to "45%"
  - `chart_color` — assign colors to categories (8-color palette)
  - `conic_gradient` — generate CSS conic-gradient for donut chart
  - `bar_style` — generate CSS height % for bar charts
  - `format_date`, `format_date_iso` — date formatting

---

### 2. **`auth_app`** — Magic Link Authentication

**Views:**
- `auth_view()` — GET `/login`, POST `/login` (unified login + registration)
- `verify_magic_link()` — GET `/auth/verify?token=xxx`
- `logout_view()` — POST `/logout`
- `session_status()` — GET `/api/session-status` (JSON, for timeout warnings)

**Services:**
- `AuthService.request_login_link()` — Generate token, send email (or log in dev)
- `AuthService.verify_magic_link()` — Validate token, create session
- Rate limiting: 5-min cooldown, 3/day per email, 50/day global

**Anti-bot:**
- Honeypot field "website" (must be empty)
- Form submission timing check (must take > 2 seconds)

**Unique index on email:**
```sql
CREATE UNIQUE INDEX idx_user_email_lower ON core_user (LOWER(email))
```

---

### 3. **`dashboard`** — Home Page Aggregation

**Views:**
- `home()` — GET `/` (main dashboard page)
- `recent_transactions_partial()` — GET `/partials/recent-transactions`
- `people_summary_partial()` — GET `/partials/people-summary`
- `net_worth_breakdown_partial()` — GET `/dashboard/net-worth/<type>`

**Services:**
- `DashboardService.build()` — Aggregates all data:
  - Net worth (accounts + virtual accounts + investments)
  - Spending velocity (6-month trend, daily avg projection)
  - Budget progress (current month status)
  - CC summary (utilization, due dates, payments)
  - Health warnings (min balance violations)
  - People summary (outstanding loans/debts)
  - Daily snapshots (30-day sparkline data)
  - Habit streak (consecutive days with transactions)

---

### 4. **`accounts`** — Accounts & Institutions Management

**Views:** ~25 routes (CRUD, forms, presets, JSON API)

**Services:**
- `InstitutionService` — CRUD for institutions, reordering
- `AccountService` — CRUD for accounts, balance history, utilization trends, health checks

**Key methods:**
- `get_balance_history(account_id, days=30)` — 30-day sparkline
- `get_utilization_history(account_id, days=30)` — CC utilization trend
- `get_recent_transactions(account_id, limit=10)` — Account detail page
- `get_linked_virtual_accounts(account_id)` — Find VAs linked to account
- `toggle_dormant(account_id)` — Hide inactive accounts

**Data:**
- `institution_data.py` — Preset banks, fintechs, wallets (icons, names)

---

### 5. **`transactions`** — Transactions, Transfers, Exchanges

**Views:** ~24 routes

**Services:**
- `TransactionService` — CRUD with atomic balance updates:
  - `create()` — expense/income with balance delta
  - `update()` — inline edit, recalculate balance deltas
  - `delete()` — reverse balance updates
  - `create_transfer()` — debit/credit pair with optional fee
  - `create_exchange()` — cross-currency with rate
  - `allocate_to_virtual_account()` — Tag transaction for VA
  - `deallocate_from_virtual_accounts()` — Remove VA allocation
  - `batch_create()` — Multiple transactions, all-or-nothing atomicity
  - `get_filtered_enriched()` — Advanced filtering (account, category, type, date, search)
  - `suggest_category()` — AI category suggestion from description

**Key patterns:**
- All balance updates wrapped in `transaction.atomic()`
- Currency enforced from account (never trust form)
- Balance delta tracked for reconciliation
- Transfers create two linked transaction rows
- Exchanges include rate for historical reference

---

### 6. **`reports`** — Monthly Spending Reports

**Views:**
- `reports_page()` — GET `/reports` (with month/currency/account filters)

**Services:**
- `get_monthly_report()` — Full report builder:
  - Spending by category with percentages
  - 6-month history (income vs expenses)
  - Chart segments for donut and bar charts

---

### 7. **`budgets`** — Budget Management

**Views:** 5 routes (CRUD, total budget)

**Services:**
- `BudgetService` — Create, read, delete budgets
- `get_all_with_spending()` — Annotate budgets with current month spending

**Status logic:**
- Green: < 80%
- Amber: 80–99%
- Red: >= 100%

---

### 8. **`people`** — Loan & Debt Tracking

**Views:** 8 routes (list, detail, loan/repay)

**Services:**
- `PersonService` — CRUD with atomic loan recording:
  - `record_loan()` — Create loan_out or loan_in transaction
  - `record_repayment()` — Repayment with direction detection
  - `get_debt_summary()` — Per-currency breakdown, progress %, payoff date

---

### 9. **`virtual_accounts`** — Envelope Budgeting

**Views:** 11 routes (CRUD, allocate, archive)

**Services:**
- `VirtualAccountService` — Envelope management:
  - `get_allocations()` — Merge transaction + direct allocations
  - `allocate_to_virtual_account()` — Tag transaction
  - `direct_allocate()` — Manual contribution/withdrawal
  - `_recalculate_balance()` — Recompute from allocations

---

### 10. **`recurring`** — Recurring Transaction Rules

**Views:** 5 routes (CRUD, confirm, skip)

**Services:**
- `RecurringService` — Template-based recurring transactions:
  - `create()` — Store rule with template JSON
  - `get_due_pending()` — Rules with next_due_date <= today
  - `confirm()` — Create transaction, advance due date
  - `skip()` — Advance due date (no transaction)

---

### 11. **`investments`** — Investment Portfolio

**Views:** 4 routes (CRUD)

**Services:**
- `InvestmentService` — Holdings with computed valuations

---

### 12. **`settings_app`** — Settings, Categories, Export

**Views:** 9 routes (settings, categories CRUD, CSV export)

**Services:**
- `CategoryService` — CRUD for custom categories
- `SettingsService` — User preferences (dark mode, notifications)
- `CSVExporter` — Transaction export

---

### 13. **Other Apps**

- **`categories`** — Category JSON API (`/api/categories`)
- **`exchange_rates`** — Exchange rate reference data
- **`push`** — Web push notifications (VAPID, subscriptions, polling)
- **`jobs`** — Background management commands:
  - `run_startup_jobs` — cleanup_sessions → process_recurring → reconcile_balances → refresh_views → take_snapshots

---

## Architectural Patterns

### 1. **Service Layer**
Every app has `services.py` with business logic. Views are thin (just request validation + response formatting).

```python
# transactions/services.py
class TransactionService:
    @staticmethod
    def create(user_id, account_id, amount, category_id, ...):
        """Create expense/income with atomic balance update."""
        with transaction.atomic():
            tx = Transaction.objects.create(...)
            account.current_balance += balance_delta
            account.save()
            return tx
```

---

### 2. **User-Scoped Queries**
All queries filtered by `user_id` for per-user data isolation. Custom manager:

```python
# core/managers.py
class UserScopedManager(models.Manager):
    def for_user(self, user_id):
        return self.filter(user_id=user_id)

# Usage in views:
transactions = Transaction.objects.for_user(request.user_id)
```

---

### 3. **Atomic Transactions**
Balance updates, recurring confirmations, transfers all wrapped in `transaction.atomic()` to prevent race conditions.

```python
with transaction.atomic():
    account.current_balance -= amount
    account.save()
    tx = Transaction.objects.create(...)
```

---

### 4. **HTMX Partials**
Many views return HTML fragments (not full pages) for modal/sheet swaps.

```python
# Returns partial HTML for bottom sheet
return render(request, 'accounts/_form.html', {'form': form})
```

---

### 5. **JSON APIs**
Parallel `/api/*` routes for programmatic access and e2e testing.

```python
# POST /api/accounts
def api_account_list_create(request):
    if request.method == 'POST':
        return JsonResponse(AccountSerializer(account).data)
```

---

### 6. **Computed Fields**
Progress %, balances, valuations computed in service layer (not stored).

```python
# virtual_accounts/services.py
va.current_balance = sum(allocs.amount for allocs in allocations)
va.progress_pct = (va.current_balance / va.target_balance) * 100
```

---

### 7. **Denormalized Cache**
Cached fields updated atomically (account.current_balance, person.balance_egp, etc.).

```python
# On every transaction, atomically update account balance
account.current_balance += balance_delta
account.save(update_fields=['current_balance', 'updated_at'])
```

---

### 8. **Soft Deletes**
Archived categories, virtual accounts, people stay in DB (hidden from UI).

```python
is_archived = models.BooleanField(default=False)

# Query
Category.objects.for_user(user_id).filter(is_archived=False)
```

---

## Testing

**Test structure:**
- `backend/tests/factories.py` — factory_boy factories (User, Account, Transaction, etc.)
- `backend/tests/conftest.py` — pytest fixtures (auth_user, auth_cookie, auth_client)
- `<app>/tests/test_services.py` — Service layer unit tests
- `<app>/tests/test_views.py` — View/integration tests
- `e2e/tests/*.py` — Playwright end-to-end tests

**Test count:** 692+ tests passing

**Run tests:**
```bash
make test                 # Run all tests
make test-e2e            # Run Playwright e2e tests
make lint                # ruff + mypy
make run                 # Start dev server
```

---

## Middleware & Authentication

### `GoSessionAuthMiddleware` (in `core/middleware.py`)

**Flow on every request:**
1. Read `clearmoney_session` cookie
2. Look up Session row in DB
3. Validate token + expiry (not in-memory)
4. If valid: set `request.user_id`, `request.user_email`
5. If invalid/expired: clear cookie, redirect to `/login`

**Public paths** (no auth required):
- `/healthz`, `/static/`, `/login`, `/register`, `/auth/verify`, `/logout`

---

## Deployment

**Environment variables:**
- `RESEND_API_KEY` — Resend email API key (leave empty in dev to log URLs to stdout)
- `DISABLE_RATE_LIMIT` — Disable rate limiting for testing
- `DJANGO_SECRET_KEY` — Secret key for CSRF, sessions
- `DEBUG` — Debug mode (False in prod)
- `ALLOWED_HOSTS` — Comma-separated allowed hostnames
- `DATABASE_URL` — PostgreSQL connection string
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` — Web push VAPID keys

**Docker:**
```yaml
# docker-compose.yml
services:
  django:
    image: clearmoney-django
    environment:
      - DATABASE_URL=postgresql://...
      - RESEND_API_KEY=...
```

---

## Database

**PostgreSQL with:**
- UUID primary keys
- JSONB for flexible data (health constraints, CC billing cycles, template transactions)
- Materialized views for reports
- Unique constraints on critical fields

**Materialized views:**
- `mv_monthly_category_totals` — Monthly spending by category
- `mv_daily_tx_counts` — Daily transaction counts

**Startup jobs** (run on app boot):
```
cleanup_sessions
  → process_recurring (check if due, auto-confirm if enabled)
  → reconcile_balances (validate transaction sum)
  → refresh_views (refresh materialized views)
  → take_snapshots (create DailySnapshot + AccountSnapshot for sparklines)
```

---

## See Also

- [FEATURES.md](FEATURES.md) — Feature documentation
- [ROUTES.md](ROUTES.md) — Complete route inventory
- [docs/features/](features/) — Individual feature guides
- [docs/research/](research/) — UX audits and research
