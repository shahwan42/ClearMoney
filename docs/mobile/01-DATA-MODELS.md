# ClearMoney React Native — Data Models & Database Schema

Complete specification of all 18 models with fields, types, constraints, relationships, and validation rules.

**Key Principles:**
- All monetary values: `NUMERIC(15,2)` in DB → `Decimal` in Python → `string` or `float` in JSON/React Native
- All primary keys: UUID (not auto-increment integers)
- All user-scoped data includes `user_id` foreign key
- ExchangeRateLog is the exception (global data, no user_id)

---

## 1. User
**Table:** `users`
**Purpose:** Authentication, multi-user isolation

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY, `db_default=gen_random_uuid()` | Unique user identifier |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL, lower(email) indexed | Case-insensitive via DB index |
| `created_at` | TIMESTAMP | NOT NULL, `auto_now_add=True` | Registration timestamp |
| `updated_at` | TIMESTAMP | NOT NULL, `auto_now=True` | Last profile update |

**Relationships:**
- One-to-Many: Sessions, Institutions, Accounts, Categories, Persons, RecurringRules, Transactions, VirtualAccounts, Budgets, TotalBudgets, Investments, DailySnapshots, AccountSnapshots

**Business Rules:**
- No password field (magic link auth only)
- Every data row filters by `user_id`
- New user registration auto-seeds 25 default categories

---

## 2. Session
**Table:** `sessions`
**Purpose:** Server-side session management (replaces JWT)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Session ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL, indexed | User this session belongs to |
| `token` | VARCHAR(255) | UNIQUE, NOT NULL | Secure session token (urlsafe base64) |
| `expires_at` | TIMESTAMP | NOT NULL | Session expiration (30 days from creation) |
| `created_at` | TIMESTAMP | NOT NULL | Session creation timestamp |

**Business Rules:**
- Token: `secrets.token_urlsafe(32)` — cryptographically secure
- TTL: 30 days
- Client storage: httponly cookie `clearmoney_session` or Keychain/Keystore (mobile)
- Middleware validates: token exists, not expired, maps to valid user
- On logout: row deleted from DB, cookie cleared

---

## 3. AuthToken
**Table:** `auth_tokens`
**Purpose:** Short-lived magic link tokens

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Token ID |
| `email` | VARCHAR(255) | NOT NULL, lower(email) indexed | Email requested (not yet verified) |
| `token` | VARCHAR(255) | UNIQUE, NOT NULL | Magic link token |
| `purpose` | VARCHAR(20) | NOT NULL, default='login' | 'login' or 'registration' |
| `expires_at` | TIMESTAMP | NOT NULL | Expiry (15 minutes) |
| `used` | BOOLEAN | NOT NULL, default=False | Single-use enforcement |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |

**Rate Limiting:**
- Per-email: 5-minute cooldown, max 3/day
- Global: max 50/day
- Token reuse: return REUSED if unexpired token exists (no new email sent)

**Validation:**
- Token must exist, not be used, and not be expired
- On verify: set `used=True` immediately (single-use)
- For registration: email must NOT exist in users table
- For login: email must exist in users table

---

## 4. Institution
**Table:** `institutions`
**Purpose:** Groups accounts under a bank/fintech/wallet

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Institution ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL, indexed | Owner |
| `name` | VARCHAR(255) | NOT NULL | "HSBC", "Telda", "Cash" |
| `type` | VARCHAR(20) | NOT NULL, default='bank' | 'bank', 'fintech', 'wallet' |
| `color` | VARCHAR(20) | NULL | Hex color for UI (e.g., #FF5733) |
| `icon` | VARCHAR(255) | NULL | Icon name or emoji |
| `display_order` | INTEGER | NOT NULL, default=0 | Sort order in UI |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Relationships:**
- One-to-Many: Accounts

**Business Rules:**
- Case-insensitive match on (name, type); deduplicates within same user
- Manual reordering via `display_order`

---

## 5. Account
**Table:** `accounts`
**Purpose:** Single financial account (bank, credit card, cash)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Account ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL, indexed | Owner |
| `institution_id` | UUID | FOREIGN KEY → institutions(id), NOT NULL, indexed | Parent institution |
| `name` | VARCHAR(100) | NOT NULL | "Personal Savings", "Amex Black" |
| `type` | VARCHAR(20) | NOT NULL | 'savings', 'current', 'prepaid', 'cash', 'credit_card', 'credit_limit' |
| `currency` | VARCHAR(3) | NOT NULL, default='EGP' | 'EGP', 'USD' |
| `current_balance` | NUMERIC(15,2) | NOT NULL, default=0 | Cached, updated on every transaction. **Negative for credit cards** |
| `initial_balance` | NUMERIC(15,2) | NOT NULL, default=0 | Starting balance (for reconciliation) |
| `credit_limit` | NUMERIC(15,2) | NULL | For credit cards (unsigned) |
| `is_dormant` | BOOLEAN | NOT NULL, default=False | Hidden from UI when True |
| `role_tags` | TEXT[] | NULL | PostgreSQL array, e.g., ["primary", "emergency"] |
| `display_order` | INTEGER | NOT NULL, default=0 | Sort order in UI |
| `metadata` | JSONB | NULL | Billing cycle info: `{billing_cycle_day: 10, grace_days: 25}` |
| `health_config` | JSONB | NULL | Health constraints: `{min_balance: 5000, min_monthly_deposit: 10000}` |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Relationships:**
- Many-to-One: Institution, User
- One-to-Many: Transactions, AccountSnapshots

**Calculated Fields:**
- `is_credit_type()` = `type in ("credit_card", "credit_limit")`
- Display Balance = `-(current_balance)` if credit type else `current_balance`

**Business Rules:**
- Credit card balances stored as **negative numbers** (representing debt)
  - Display with `neg` filter: show abs value with label "Amount Used"
  - `current_balance = -1500` means user owes 1500
- `balance_delta` on each transaction updates `current_balance` atomically
- For credit accounts: `credit_limit` is the debt ceiling
- Dormant accounts excluded from UI (not deleted)

---

## 6. Category
**Table:** `categories`
**Purpose:** Expense/income classification

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Category ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL | Owner |
| `name` | VARCHAR(100) | NOT NULL | "Groceries", "Salary", "Rent" |
| `type` | VARCHAR(20) | NOT NULL | 'expense' or 'income' |
| `icon` | VARCHAR(10) | NULL | Unicode emoji: "🛒", "💰" |
| `is_system` | BOOLEAN | NOT NULL, default=False | Auto-seeded on registration |
| `is_archived` | BOOLEAN | NOT NULL, default=False | Soft delete |
| `display_order` | INTEGER | NOT NULL, default=0 | Sort order |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Relationships:**
- One-to-Many: Transactions

**Business Rules:**
- 25 system categories auto-seeded per new user
- Archived categories hidden from selectors but historical transactions keep reference
- UI uses `<optgroup label="Expenses">` and `<optgroup label="Income">`

---

## 7. Person
**Table:** `persons`
**Purpose:** Track people you lend to or borrow from (debt tracking)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Person ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL | Owner |
| `name` | VARCHAR(100) | NOT NULL | "Ahmed", "Mom" |
| `note` | TEXT | NULL | Notes about the relationship |
| `net_balance` | NUMERIC(15,2) | NOT NULL, default=0 | **Deprecated** — kept for backward compat |
| `net_balance_egp` | NUMERIC(15,2) | NOT NULL, default=0 | Running total owed in EGP (positive = user owes, negative = owed to user) |
| `net_balance_usd` | NUMERIC(15,2) | NOT NULL, default=0 | Running total owed in USD |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Relationships:**
- One-to-Many: Transactions

**Business Rules:**
- Positive balance = user owes the person
- Negative balance = person owes the user
- Updated atomically on `loan_out`, `loan_in`, `loan_repayment` transactions
- Two-currency tracking (EGP + USD) independent of account currency

---

## 8. RecurringRule
**Table:** `recurring_rules`
**Purpose:** Schedule recurring transactions (subscriptions)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Rule ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL | Owner |
| `template_transaction` | JSONB | NOT NULL | Serialized TransactionTemplate (all tx fields except id/timestamps) |
| `frequency` | VARCHAR(20) | NOT NULL | 'monthly' or 'weekly' |
| `day_of_month` | INTEGER | NULL | Day 1–28 for monthly frequency |
| `next_due_date` | DATE | NOT NULL | Next execution date |
| `is_active` | BOOLEAN | NOT NULL, default=True | Toggle on/off |
| `auto_confirm` | BOOLEAN | NOT NULL, default=False | Auto-apply or await user confirmation |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Relationships:**
- One-to-Many: Transactions (via recurring_rule_id, nullable)

**Business Rules:**
- `template_transaction` JSON structure:
  ```json
  {
    "type": "expense",
    "amount": "50.00",
    "currency": "EGP",
    "category_id": "uuid",
    "account_id": "uuid",
    "counter_account_id": null,
    "note": "Netflix subscription"
  }
  ```
- Cron job runs daily: check `next_due_date <= today`, execute template, update next date
- If `auto_confirm=false`, creates pending transaction awaiting user approval

---

## 9. Transaction
**Table:** `transactions`
**Purpose:** Central record for every money movement

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Transaction ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL, indexed | Owner |
| `type` | VARCHAR(30) | NOT NULL | 'expense', 'income', 'transfer', 'exchange', 'loan_out', 'loan_in', 'loan_repayment' |
| `amount` | NUMERIC(15,2) | NOT NULL | **Always positive** — sign comes from `balance_delta` |
| `currency` | VARCHAR(3) | NOT NULL | 'EGP', 'USD' |
| `account_id` | UUID | FOREIGN KEY → accounts(id), NOT NULL, indexed | Primary account |
| `counter_account_id` | UUID | FOREIGN KEY → accounts(id), NULL, indexed | For transfers/exchanges |
| `category_id` | UUID | FOREIGN KEY → categories(id), NULL, indexed | For expense/income |
| `date` | DATE | NOT NULL, indexed | Transaction date |
| `time` | TIME | NULL | Transaction time (optional) |
| `note` | TEXT | NULL | User notes |
| `tags` | TEXT[] | NOT NULL, default=[] | PostgreSQL array for filtering |
| `exchange_rate` | NUMERIC(10,4) | NULL | For multi-currency (EGP per 1 USD) |
| `counter_amount` | NUMERIC(15,2) | NULL | Amount in counter account (for transfers with exchange) |
| `fee_amount` | NUMERIC(15,2) | NULL | Transfer/exchange fee |
| `fee_account` | UUID | NULL | Account deducted from for fee |
| `balance_delta` | NUMERIC(15,2) | NOT NULL | Signed impact on account balance |
| `person_id` | UUID | FOREIGN KEY → persons(id), NULL | For loan transactions |
| `linked_transaction_id` | UUID | FOREIGN KEY → transactions(id), NULL | Reverse of a transfer |
| `recurring_rule_id` | UUID | FOREIGN KEY → recurring_rules(id), NULL | Source rule |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Relationships:**
- Many-to-One: User, Account, Counter Account, Category, Person, Recurring Rule, Linked Transaction
- One-to-Many: VirtualAccountAllocations

**Field Validation Rules:**
- `amount` must be positive; sign determined by `type` + `balance_delta`
- `balance_delta` is signed: expense = negative, income = positive, transfer source = negative
- `currency` is **server-enforced** from the account (service layer overrides form)
- `category_id` required for expense/income, forbidden for transfer/exchange
- `counter_account_id` required for transfer/exchange
- `counter_amount` required for exchange (when currency differs)
- `exchange_rate` populated for multi-currency transactions
- `person_id` set for loan-related transactions only
- `linked_transaction_id` points to reverse entry (for transfers)
- `recurring_rule_id` set if created from a recurring rule

---

## 10. VirtualAccount
**Table:** `virtual_accounts`
**Purpose:** Envelope budgeting (earmarks money without moving actual funds)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Virtual account ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL | Owner |
| `name` | VARCHAR(100) | NOT NULL | "Emergency Fund", "Vacation" |
| `target_amount` | NUMERIC(15,2) | NULL | Goal (optional, for progress tracking) |
| `current_balance` | NUMERIC(15,2) | NOT NULL, default=0 | Running total allocated |
| `icon` | VARCHAR(10) | NULL, default='' | Emoji |
| `color` | VARCHAR(20) | NULL, default='#0d9488' | Hex color |
| `is_archived` | BOOLEAN | NOT NULL, default=False | Hidden from UI |
| `exclude_from_net_worth` | BOOLEAN | NOT NULL, default=False | Skip in net worth calc |
| `display_order` | INTEGER | NOT NULL, default=0 | Sort order |
| `account_id` | UUID | FOREIGN KEY → accounts(id), NULL | Linked source account (optional) |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Relationships:**
- One-to-Many: VirtualAccountAllocations
- Many-to-One: Account (optional)

**Calculated Field:**
- `progress_pct()` = `(current_balance / target_amount) * 100` (returns 0 if no target)

---

## 11. VirtualAccountAllocation
**Table:** `virtual_account_allocations`
**Purpose:** Pivot table linking transactions to virtual accounts

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Allocation ID |
| `transaction_id` | UUID | FOREIGN KEY → transactions(id), NULL | Source transaction (nullable for manual allocations) |
| `virtual_account_id` | UUID | FOREIGN KEY → virtual_accounts(id), NOT NULL | Target envelope |
| `amount` | NUMERIC(15,2) | NOT NULL | Positive = contribution, negative = withdrawal |
| `note` | TEXT | NULL | Why allocated |
| `allocated_at` | DATE | NULL | Allocation date |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |

**Relationships:**
- Many-to-One: Transaction (optional), VirtualAccount

**Business Rules:**
- One transaction can be split across multiple virtual accounts
- Manual allocations: `transaction_id = NULL`, user enters amount directly
- Running balance updates: query sum of allocations where `virtual_account_id = X`

---

## 12. Budget
**Table:** `budgets`
**Purpose:** Monthly spending limit per category

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Budget ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL, indexed | Owner |
| `category_id` | UUID | FOREIGN KEY → categories(id), NOT NULL | Target category |
| `monthly_limit` | NUMERIC(15,2) | NOT NULL | Spending cap |
| `currency` | VARCHAR(3) | NOT NULL, default='EGP' | 'EGP', 'USD' |
| `is_active` | BOOLEAN | NOT NULL, default=True | Toggle on/off |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Constraints:**
- UNIQUE: (user_id, category_id, currency) — one budget per category per currency

**Relationships:**
- Many-to-One: User, Category

---

## 13. TotalBudget
**Table:** `total_budgets`
**Purpose:** Overall monthly spending cap per currency

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Budget ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL, indexed | Owner |
| `monthly_limit` | NUMERIC(15,2) | NOT NULL | Total spending cap |
| `currency` | VARCHAR(3) | NOT NULL, default='EGP' | 'EGP', 'USD' |
| `is_active` | BOOLEAN | NOT NULL, default=True | Toggle on/off |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Constraints:**
- UNIQUE: (user_id, currency) — one total budget per currency per user

---

## 14. Investment
**Table:** `investments`
**Purpose:** Track fund holdings on investment platforms

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Investment ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL | Owner |
| `platform` | VARCHAR(100) | NOT NULL, default='Thndr' | "Thndr", "EFawry" |
| `fund_name` | VARCHAR(100) | NOT NULL | "FLEX Income", "EFG-Hermes Dividend" |
| `units` | NUMERIC(15,4) | NOT NULL, default=0 | Number of units held |
| `last_unit_price` | NUMERIC(15,4) | NOT NULL, default=0 | Latest unit price |
| `currency` | VARCHAR(3) | NOT NULL, default='EGP' | 'EGP', 'USD' |
| `last_updated` | TIMESTAMP | NOT NULL | Last price update |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL | Last update |

**Calculated Field:**
- `valuation()` = `units * last_unit_price`

---

## 15. DailySnapshot
**Table:** `daily_snapshots`
**Purpose:** Append-only daily financial state (for sparklines, MoM comparisons)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Snapshot ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL, indexed | Owner |
| `date` | DATE | NOT NULL, indexed | Snapshot date |
| `net_worth_egp` | NUMERIC(15,2) | NOT NULL, default=0 | Total assets in EGP |
| `net_worth_raw` | NUMERIC(15,2) | NOT NULL, default=0 | Net worth before exchange rate conversion |
| `exchange_rate` | NUMERIC(10,4) | NOT NULL, default=0 | USD to EGP rate on that day |
| `daily_spending` | NUMERIC(15,2) | NOT NULL, default=0 | Spending that day |
| `daily_income` | NUMERIC(15,2) | NOT NULL, default=0 | Income that day |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |

**Constraints:**
- UNIQUE: (user_id, date) — one snapshot per user per day

**Business Rules:**
- Append-only: once written, never updated
- Daily cron: `take_snapshots()` job sums account balances + calculates spending/income

---

## 16. AccountSnapshot
**Table:** `account_snapshots`
**Purpose:** Per-account daily balance (for balance sparklines)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Snapshot ID |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL | Owner |
| `date` | DATE | NOT NULL | Snapshot date |
| `account_id` | UUID | FOREIGN KEY → accounts(id), NOT NULL | Account being tracked |
| `balance` | NUMERIC(15,2) | NOT NULL, default=0 | Balance on that date |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |

**Constraints:**
- UNIQUE: (user_id, date, account_id) — one snapshot per account per day

**Business Rules:**
- Append-only: one historical balance per account per day
- Used for balance sparklines in UI
- Query last 90 days for chart

---

## 17. ExchangeRateLog
**Table:** `exchange_rate_log`
**Purpose:** Append-only daily USD/EGP rate history (global data, no user_id)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Log entry ID |
| `date` | DATE | NOT NULL | Rate date |
| `rate` | NUMERIC(10,4) | NOT NULL | EGP per 1 USD (e.g., 50.5 = 1 USD costs 50.5 EGP) |
| `source` | VARCHAR(50) | NULL | "CBE" (Central Bank of Egypt), "XE", etc. |
| `note` | TEXT | NULL | Additional context |
| `created_at` | TIMESTAMP | NOT NULL | Creation timestamp |

**Business Rules:**
- **No user_id** — global reference data
- Append-only
- Rate = EGP per 1 USD (conversion: amount_USD * rate = amount_EGP)

---

## 18. UserConfig
**Table:** `user_config`
**Purpose:** Legacy single-user config (kept for backward compatibility)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | Config ID |
| `pin_hash` | TEXT | NOT NULL | Hashed PIN (if biometric auth used) |
| `session_key` | TEXT | NOT NULL | Session tracking |
| `failed_attempts` | INTEGER | NOT NULL, default=0 | Brute-force protection counter |
| `locked_until` | TIMESTAMP | NULL | Brute-force lock expiry |
| `created_at` | TIMESTAMP | NULL | Creation timestamp |
| `updated_at` | TIMESTAMP | NULL | Last update |

**Notes:**
- Deprecated — kept for legacy support
- Not actively used in current magic link flow

---

## Summary

| Model | Records | Purpose |
|-------|---------|---------|
| User | N users | Auth, data isolation |
| Session | N*30 | Server-side session management |
| AuthToken | N*100 (short-lived) | Magic link tokens |
| Institution | N*10 | Account grouping |
| Account | N*20 | Financial accounts (balance tracked) |
| Category | N*35 | Transaction classification |
| Person | N*20 | Debt tracking |
| RecurringRule | N*20 | Scheduled transactions |
| **Transaction** | **N*1000s** | **Every money movement** |
| VirtualAccount | N*10 | Envelope budgeting |
| VirtualAccountAllocation | N*1000s | Transaction allocation splits |
| Budget | N*40 | Category limits |
| TotalBudget | N*2 | Global limit per currency |
| Investment | N*10 | Fund holdings |
| DailySnapshot | N*1000 | Daily net worth (append-only) |
| AccountSnapshot | N*10000 | Daily balance per account (append-only) |
| ExchangeRateLog | 1000s | USD/EGP history (global) |
| UserConfig | N | Legacy brute-force protection |

---

## Data Type Mapping (DB → Python → JSON/RN)

| Database Type | Python | JSON/API | React Native | Notes |
|---------------|--------|----------|--------------|-------|
| UUID | `uuid.UUID` | `"string"` (UUID format) | String | Use `react-native-uuid` or native UUID lib |
| VARCHAR(n) | `str` | `string` | String | Max lengths vary per field |
| TEXT | `str` | `string` | String | Unbounded |
| NUMERIC(15,2) | `Decimal` | `string` or `float` | String (preferred) | **Never use JS Number for money** |
| NUMERIC(10,4) | `Decimal` | `string` or `float` | String | Exchange rates, unit prices |
| DATE | `datetime.date` | `"YYYY-MM-DD"` | String (ISO 8601) | Use `date-fns` or native Date |
| TIME | `datetime.time` | `"HH:MM:SS"` | String (ISO 8601) | Optional |
| TIMESTAMP | `datetime.datetime` | `"ISO 8601"` | String or Number | E.g., `"2026-03-25T14:30:00Z"` |
| BOOLEAN | `bool` | `boolean` | Boolean | |
| TEXT[] | `list[str]` | `["item1", "item2"]` | Array<string> | PostgreSQL array |
| JSONB | `dict` | `object` | Object | Parse JSON from API |

---

## Special Data Handling

### Credit Card Balances
- **Stored as negative:** `current_balance = -1500` means user owes 1500
- **Display logic:**
  - Show: `abs(current_balance)` with label "Amount Used"
  - If no limit: show debt as-is
  - If limit set: utilization = `(abs(current_balance) / credit_limit) * 100`

### Decimal Arithmetic (Critical for Correctness)
- **Never use JavaScript floats for money**
- Use `decimal.js`, `big.js`, or `ts-decimal` in React Native
- Exchange rates: NUMERIC(10,4) — 4 decimal places
- Monetary values: NUMERIC(15,2) — 2 decimal places
- Always round to 2 decimals after calculations

### ArrayField (PostgreSQL TEXT[])
- Stored in DB as `ARRAY['tag1', 'tag2']`
- API returns as JSON: `["tag1", "tag2"]`
- In React Native: Array<string>

### JSONB Fields
- `Account.metadata`: Billing cycle info
  ```json
  {
    "billing_cycle_day": 10,
    "grace_days": 25,
    "interest_free_period_days": 0
  }
  ```
- `Account.health_config`: Health constraints
  ```json
  {
    "min_balance": 5000,
    "min_monthly_deposit": 10000
  }
  ```
- `RecurringRule.template_transaction`: Serialized transaction template
  ```json
  {
    "type": "expense",
    "amount": "50.00",
    "currency": "EGP",
    "category_id": "uuid",
    "account_id": "uuid",
    "note": "Netflix"
  }
  ```

---

## Unique Constraints & Indexes

| Table | Constraint | Type | Notes |
|-------|-----------|------|-------|
| users | (email) | UNIQUE | Case-insensitive via DB index |
| sessions | (token) | UNIQUE | One active session per token |
| auth_tokens | (token) | UNIQUE | One magic link per token |
| budgets | (user, category, currency) | UNIQUE | One budget per category per currency |
| total_budgets | (user, currency) | UNIQUE | One total budget per currency |
| daily_snapshots | (user, date) | UNIQUE | One snapshot per day |
| account_snapshots | (user, date, account) | UNIQUE | One balance per account per day |

### Indexed Columns (for query performance)
- `users.email`
- `sessions.user_id`, `sessions.token`
- `auth_tokens.token`
- `accounts.user_id`, `accounts.institution_id`
- `categories.user_id`
- `transactions.user_id`, `transactions.account_id`, `transactions.category_id`, `transactions.date`
- `persons.user_id`
- `institutions.user_id`
- `daily_snapshots.user_id`, `daily_snapshots.date`
- `budgets.user_id`
- `total_budgets.user_id`
- `investments.user_id`
- `virtual_accounts.user_id`

---

## Per-User Data Isolation

Every table except `ExchangeRateLog` includes `user_id`. All queries are scoped:

```sql
SELECT * FROM transactions WHERE user_id = ? AND date >= ?
SELECT * FROM accounts WHERE user_id = ? AND is_dormant = false
SELECT * FROM categories WHERE user_id = ? AND is_archived = false
```

**Implementation:** Django uses `UserScopedManager()` custom manager — queries can't accidentally leak data.

**In React Native:** All API endpoints should enforce `user_id` from session/token. Never trust user_id from form input.

---

## Migration Strategy for React Native

1. **Replicate exact field names and types** — use this spec as source of truth
2. **Implement models in order:** User → Session → AuthToken → Institution → Account → (others)
3. **Set up relationships first** — foreign keys must exist before inserting dependent data
4. **Test decimal handling** — verify NUMERIC(15,2) precision with test amounts (0.01, 999999999.99)
5. **Validate against running Django** — use Django's schema as reference during development
6. **Implement per-user scoping** — all queries must filter by authenticated user_id
7. **Use Decimal library** — not JavaScript Number, for all monetary values

---

**Generated from production Django codebase on 2026-03-25**
