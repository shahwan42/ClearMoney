# ClearMoney React Native — Business Rules, Validation & Edge Cases

Comprehensive specification extracted from 40+ test files covering validation rules, edge cases, boundary conditions, state consistency, and error handling.

---

## 1. Account Management

### Account Creation
- **Name:** If blank/whitespace, auto-generate as `{Institution.name} - {Type}`
- **Currency:** Enforced from account record; form value ignored
- **Account Types:** `savings`, `current`, `prepaid`, `cash`, `credit_card`, `credit_limit`
- **Dormant Flag:** Dormant accounts excluded from UI dropdowns and net worth
- **Credit Limit:** Nullable; required only for credit card types

### Credit Card Accounts
- **is_credit_type()** Returns true for `credit_card` and `credit_limit`
- **Balance Signs:** Debt stored as **negative numbers**
  - Example: `-5000` means owing 5000 (display as "5000 used")
- **Utilization Calc:** `|balance| / credit_limit * 100%` (only count if negative)
- **Credit Limit Enforcement:**
  - Reject expense if: `new_balance < -credit_limit`
  - Available credit: `credit_limit + current_balance`
- **Billing Cycle (Metadata):**
  - statement_day: Day statement period ends (e.g., 15th)
  - due_day: Payment due day (e.g., 5th of next month)
  - **Due Soon Alert:** If `days_until_due ≤ 7`
  - **Interest-Free Period:** Always 55 days from statement_day
  - **Remaining Days:** `max(0, statement_end + 55 - today)`

### Institution Deduplication
- **Case-Insensitive Match:** (name, type) lookup; creates or reuses
- **Different Types Allowed:** Same name, different type = separate institution
- **Display Order:** Manually reorderable; default=0

---

## 2. Transaction Validation & Rules

### Core Validation Rules

| Field | Rule | Error |
|-------|------|-------|
| `amount` | Must be > 0 | "Amount must be positive" |
| `type` | Valid enum (expense, income, transfer, exchange, loan_out, loan_in, loan_repayment) | "Invalid transaction type" |
| `account_id` | Required; must belong to user | "Account is required" or "Account not found" |
| `currency` | Enforced from account (never trust form) | N/A (server-side only) |
| `category_id` | Required for expense/income; forbidden for transfer/exchange | "Category is required" (expense) or "Category not allowed" (transfer) |
| `counter_account_id` | Required for transfer/exchange | "Destination account required" |
| `person_id` | Required for loan transactions | "Person is required" (loan) |
| `date` | Defaults to today if not provided | N/A (server-side) |
| `exchange_rate` | Required for multi-currency; must be > 0 | "Exchange rate required" |
| `counter_amount` | Required for exchange if currencies differ | "Counter amount required" |
| `fee_amount` | Must be >= 0 if provided | "Fee must be non-negative" |

### Balance Delta Calculation

**Definition:** Signed change to account balance from transaction

| Type | Formula | Example |
|------|---------|---------|
| Expense | `balance_delta = -amount` | Amount 100 → delta -100 |
| Income | `balance_delta = +amount` | Amount 100 → delta +100 |
| Transfer (source) | `balance_delta = -amount` | Amount 1000 → delta -1000 |
| Transfer (dest) | `balance_delta = +amount` | Amount 1000 → delta +1000 |
| Exchange (source) | `balance_delta = -amount` (EGP) | 10000 EGP → delta -10000 |
| Exchange (dest) | `balance_delta = +counter_amount` (USD) | 327 USD → delta +327 |

### Running Balance (Window Function)

**Query:** Aggregate preceding transactions, newest-first
```sql
running_balance = SUM(balance_deltas) OVER (PARTITION BY account_id ORDER BY date DESC, created_at DESC)
```

**Example:**
- Current balance: 5000
- Two earlier transactions: +1000, -500
- Latest tx's running_balance: 5000 (current)
- Next older tx's running_balance: 4000
- Oldest tx's running_balance: 5500

### Currency Override (Critical)

**Rule:** Service layer enforces account's currency; form value ignored

**Scenario:**
```
POST /api/transactions {
  account_id: "usd-account-uuid",
  currency: "EGP",  // ← IGNORED
  amount: 100
}
// Service overrides → currency = "USD" from account
```

### Credit Card Limit Enforcement

```python
if account.type in ('credit_card', 'credit_limit'):
    available = account.credit_limit + account.current_balance
    if amount > available:
        raise ValidationError(f"Exceeds credit limit (available: {available})")
```

**Example:**
- Limit: 50000, Balance: -15000 (owing 15000)
- Available: 50000 + (-15000) = 35000
- Trying to charge 40000 → REJECT

---

## 3. Transfer Rules

### Same Account Check
- **Rule:** Cannot transfer to same account
- **Validation:** `from_account_id != to_account_id`
- **Error:** "Cannot transfer to same account"

### Cross-Currency Transfer (Exchange)
- **Requirement:** Requires `exchange_rate` or `counter_amount` to resolve third variable
- **Validation:** Requires ≥2 of 3 variables: (amount, rate, counter_amount)
- **Formula:** `counter_amount = amount * exchange_rate`

**Example:**
- From: 10000 EGP
- Rate: 30.5 EGP/USD
- Counter: AUTO CALC → 327.87 USD

### Fee Handling
- **Optional:** `fee_amount` (≥0) deducted from source account
- **Zero Fee:** No extra transaction created
- **Positive Fee:** Creates separate "Transfer fee" expense in Fees & Charges category
- **Fee Deduction:**
  - Instapay < 1000 EGP: 0.5 EGP
  - Instapay 1000–50000: 0.1% of amount
  - Instapay > 50000: capped at 20.0 EGP

### Linked Transactions
- **Pair Creation:** Both debit + credit created atomically
- **Link Field:** `linked_transaction_id` references reverse entry
- **Cascading Delete:** Deleting one deletes both, reverses both balances

**Example:**
```
TX1: transfer, account_a, amount 1000, balance_delta -1000, linked_tx2_id
TX2: transfer, account_b, amount 1000, balance_delta +1000, linked_tx1_id
```

---

## 4. Exchange Transactions

### Rate Definition
**EGP per 1 USD** (e.g., 50.5 = 1 USD costs 50.5 EGP)

### Counter Amount
**Tracked separately** from calculated conversion to allow asymmetric exchanges

```
POST /api/transactions/exchange {
  from_amount: 10000,      // EGP
  exchange_rate: 30.5,     // EGP per 1 USD
  counter_amount: 327.87   // USD (calculated or provided)
}
```

### Precision
- **Rates:** NUMERIC(10,4) — 4 decimal places
- **Amounts:** NUMERIC(15,2) — 2 decimal places

---

## 5. People & Loans

### Multi-Currency Tracking
- **net_balance_egp:** Running total owed in EGP
- **net_balance_usd:** Running total owed in USD
- **Stored Separately:** Not converted; independent tracking

### Loan Types
| Type | Impact | Balance Change |
|------|--------|-----------------|
| `loan_out` | Person owes me money | person_balance += amount |
| `loan_in` | I owe person money | person_balance -= amount |
| `loan_repayment` | Reduce debt | Toward zero |

### Repayment Direction
- **Person owes me 1000 EGP** (balance = +1000)
  - Repay 400 → balance now 600 (person still owes 600)
  - Account balance: +400 income
- **I owe person 1000 EGP** (balance = -1000)
  - Repay 400 → balance now -600 (I still owe 600)
  - Account balance: -400 expense

### Validation
- **Amount:** Must be > 0
- **Type:** Only `loan_out` or `loan_in`
- **Currency:** Enforced from account (override rule applies)

---

## 6. Budget Rules

### Monthly Scope
- **Boundary:** Calendar month in user's timezone
- **Spending:** Aggregates `amount` from expense transactions in category

### Uniqueness
- **Constraint:** One budget per (user_id, category_id, currency)
- **Same Category, Different Currency:** Allowed (separate budgets)

### Status Calculation
```
percentage = (spent / limit) * 100
status = "green"  if percentage < 80
         "amber"  if 80 <= percentage < 100
         "red"    if percentage >= 100
```

### Validation
- **Limit:** Must be > 0
- **Category:** Required
- **Duplicate:** Reject if budget exists for category+currency

---

## 7. Virtual Accounts (Envelope Budgeting)

### Allocations
- **Pivot Table:** Links transactions to VAs (can split one tx across many VAs)
- **Non-Transactional:** Can exist without transaction (direct allocations)
- **Amount Sign:** Positive = contribution, negative = withdrawal

### Progress Tracking
```
progress % = (current_balance / target_amount) * 100
           = 0 if no target_amount
```

### Over-Allocation Warning
- **Check:** `total_va_balance > linked_account_balance`
- **Show Warning:** On dashboard and VA detail

### Cascade Delete
- **Delete VA:** All allocations cascade delete
- **Allocations Remain:** If VA deleted (SET_NULL on FK)

---

## 8. Recurring Rules

### Frequency & Scheduling
- **Frequency:** `monthly` or `weekly`
- **Monthly:** `day_of_month` (1–28) with month-end handling
- **Weekly:** Always 7 days advance

### Template Storage
**JSONB Structure:**
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

### Auto-Confirm
- **False:** Creates pending transaction in UI; user must confirm/skip
- **True:** Auto-executes; transaction created automatically

### Advance Logic
- **Monthly:** Add 1 month (handles month-end edge cases)
- **Weekly:** Add 7 days

---

## 9. Exchange Rates (Global Data)

### Rate Logging
- **Append-Only:** Never updated; only inserted
- **Global:** No user_id (shared across all users)
- **Rate Definition:** EGP per 1 USD

### Precision
- **NUMERIC(10,4):** 4 decimal places

---

## 10. Data Isolation & Security

### Per-User Filtering
**Critical Requirement:** Every query must filter by `user_id`

```python
# ✓ Correct
accounts = Account.objects.for_user(user_id)

# ✗ Wrong — leaks data
accounts = Account.objects.all()
```

### Service Layer Pattern
```python
class AccountService:
    def __init__(self, user_id: UUID):
        self.user_id = user_id

    def get_accounts(self):
        return Account.objects.for_user(self.user_id)
```

### Ownership Validation
```python
def delete_transaction(user_id: UUID, tx_id: UUID):
    tx = Transaction.objects.for_user(user_id).get(id=tx_id)  # Already scoped
    tx.delete()  # Safe — user owns it
```

---

## 11. Numeric Handling & Precision

### Decimal Arithmetic
- **Never use JavaScript floats for money**
- **Use Decimal library:** decimal.js, big.js, or ts-decimal
- **Storage:** NUMERIC(15,2) in DB → Decimal in Python → string in JSON

### Credit Card Utilization
```
utilization = abs(balance) / credit_limit * 100
            = 0 if balance >= 0 (prepaid)
            = 0 if credit_limit is null
```

### Rounding
- **Monetary:** Round to 2 decimals after calc
- **Rates:** Store as NUMERIC(10,4); round at boundary

### Reconciliation Tolerance
- **Tolerance:** ±0.005 (floating-point noise)
- **Diffs < tolerance:** Silently ignored
- **Diffs >= tolerance:** Flag as discrepancy

---

## 12. Date & Time Handling

### Timezone Awareness
- **App Timezone:** Africa/Cairo (ZoneInfo)
- **Database:** UTC (auto-conversion by Django)
- **Billing Cycles:** Computed in user's local timezone

### Month Boundaries
- **Period:** First day of month to last day (calendar month)
- **Computed:** In user's timezone

### Streaks
- **Consecutive Days:** Based on transaction `date` field
- **Counting:** Count unique dates with transactions

---

## 13. Cascading Operations

### Delete Transaction
1. Reverse balance_delta on account (atomic)
2. If linked (transfer): delete partner + reverse its balance
3. Delete VA allocations (FK cascade)
4. Do NOT delete recurring rule (nullable FK)

### Delete Account
1. Delete all transactions (FK cascade)
2. Delete all VA allocations (cascade)
3. Reverse balance impact atomically
4. Alert user if VAs lose target account

### Delete Category
1. Orphan transactions (SET_NULL on category_id)
2. Delete associated budget (FK cascade)
3. Recurring templates keep category_id in JSONB (no change)

### Delete Person
1. Orphan all transactions (SET_NULL on person_id)
2. Loan balances reset to zero (implicit)

---

## 14. Background Jobs & Reconciliation

### Daily Startup Jobs
1. **cleanup_sessions:** Delete expired sessions (expires_at < now)
2. **process_recurring:** Auto-confirm due recurring rules
3. **reconcile_balances:** Detect/fix balance discrepancies
4. **refresh_views:** Materialize views (mv_monthly_category_totals, mv_daily_tx_counts)
5. **take_snapshots:** Create DailySnapshot + AccountSnapshot for today

### Reconciliation
```python
expected = initial_balance + SUM(balance_deltas)
if abs(expected - current_balance) >= 0.005:
    # Discrepancy detected
    if auto_fix:
        current_balance = expected
```

---

## 15. Validation Summary (55+ Rules)

| Field | Validation | Error Message |
|-------|-----------|---------------|
| Amount | > 0 | "Amount must be positive" |
| Type | Valid enum | "Invalid transaction type" |
| Account | Exists + belongs to user | "Account not found" |
| Category | Exists if provided | "Category not found" |
| Transfer same account | False | "Cannot transfer to same account" |
| Credit limit | balance >= -limit | "Exceeds credit limit" |
| Budget limit | > 0 | "Limit must be positive" |
| Budget category | Unique per currency | "Budget already exists" |
| Virtual account name | Non-blank | "Name is required" |
| Person name | Non-blank | "Name is required" |
| Loan type | loan_out \| loan_in | "Invalid loan type" |
| Loan amount | > 0 | "Amount must be positive" |
| Recurring frequency | monthly \| weekly | "Invalid frequency" |
| Fee amount | >= 0 | "Fee must be non-negative" |
| Email | Non-empty, valid format | "Email is required" |
| Token | Not used, not expired | "Token invalid or expired" |

---

## 16. State Consistency Requirements

### Atomicity
- **Every transaction:** Balance update + tx creation must both succeed or both fail
- **Transfer:** Both debit + credit created atomically or both rolled back
- **Recurring confirm:** Tx creation + next_due_date advance atomic

### Denormalized Fields (Must Stay Synced)
- **Account.current_balance:** Updated on every transaction; reconciled daily
- **Person.net_balance_egp/usd:** Updated on loan/repayment
- **VirtualAccount.current_balance:** Updated via allocations
- **Daily Snapshots:** Recalculated daily as append-only

### No Orphans
- Transactions always have `account_id` (FK constraint)
- Categories always have `user_id` (FK constraint)
- Accounts always have `user_id` and `institution_id` (FK constraints)

---

## 17. Error Recovery

### User-Recoverable
- Validation errors → fix form, retry
- Duplicate budget → different category or currency
- Insufficient balance → adjust amount

### System-Level
- Reconciliation failure → auto-fix corrects balance
- Session expiry → re-authenticate
- Snapshot collision → rollback or skip (logged)

### User Can Undo
- Delete transaction → only way to undo; reverses balance

---

## 18. What Must Never Be Deleted (Data Retention)

- **Users:** Soft-delete or full cascade (per privacy policy)
- **Exchange Rates:** Append-only; never deleted (historical record)
- **Account Snapshots:** Append-only; never deleted (audit trail)
- **Daily Snapshots:** Append-only; never deleted (net worth history)
- **Transactions:** Can be deleted by user; affects balance; no recovery
- **Sessions:** Auto-cleanup after expiry
- **Auth Tokens:** Auto-cleanup after use

---

**Extracted from production codebase on 2026-03-25 — 40+ test files analyzed**
