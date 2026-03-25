# ClearMoney React Native — Complete API Specification

All endpoints documented with request/response formats, validation rules, error handling, rate limits, and mobile-specific notes.

---

## 1. Authentication API

### POST /login (Unified Login/Registration)
**Auth:** No
**Rate Limit:** `login_rate` (5 req/min per IP)

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 - Check Email):**
```json
{
  "status": "link_sent|already_registered|reused",
  "message": "Check your email for a sign-in link"
}
```

**Response (429 - Rate Limited):**
```json
{
  "error": "Too many requests. Please wait a few minutes.",
  "retry_after": 300
}
```

**Validation:**
- Email required
- Anti-bot: honeypot + timing (web only, skip for mobile API)
- Rate limits: 5-min cooldown, 3/day per email, 50/day global

**Business Logic:**
- Email doesn't exist? Create user + seed 25 categories
- Email exists? Return REUSED if unexpired token exists (no new email)
- Otherwise: Generate token, send email
- Always show "check your email" (never reveal if user exists)

---

### GET /api/auth/verify-token (Mobile)
**Auth:** No
**Rate Limit:** `login_rate`

**Query Parameters:**
```
?token=<token>
```

**Response (200):**
```json
{
  "session_token": "...",
  "user_id": "...",
  "email": "user@example.com",
  "is_new_user": false
}
```

**Response (400/401):**
```json
{
  "error": "Invalid or expired link"
}
```

**Business Logic:**
- Validate token (exists, not used, not expired)
- Mark token `used=True` (single-use)
- Create session
- Return session_token for mobile storage in Keychain/Keystore

---

### POST /api/logout
**Auth:** Yes (Bearer token)
**Rate Limit:** `general_rate`

**Headers:**
```
Authorization: Bearer ${session_token}
```

**Response (200):**
```json
{
  "status": "ok"
}
```

**Business Logic:**
- Delete session from DB
- Mobile: clear stored token

---

### GET /api/session-status
**Auth:** Yes (Bearer token)
**Rate Limit:** `general_rate`

**Response (200):**
```json
{
  "expires_in_seconds": 1800,
  "user_id": "...",
  "email": "..."
}
```

**Response (401):**
```json
{
  "error": "Session invalid or expired"
}
```

**Mobile Use:** Call every 5 minutes to check expiry, warn user if < 5 min remaining

---

## 2. Accounts & Institutions API

### GET /api/institutions
**Auth:** Yes
**Rate Limit:** `api_rate`

**Response (200):**
```json
[
  {
    "id": "uuid",
    "name": "HSBC Egypt",
    "type": "bank|fintech|wallet",
    "color": "#003DA5",
    "icon": "cib.svg",
    "display_order": 0,
    "created_at": "2026-03-20T10:00:00Z"
  }
]
```

---

### POST /api/institutions
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "name": "Chase Bank",
  "type": "bank|fintech|wallet",
  "icon": "chase.svg",
  "color": "#117DBA"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "name": "Chase Bank",
  ...
}
```

**Validation:**
- Name required, non-empty
- Type must be: bank, fintech, wallet

---

### GET /api/accounts
**Auth:** Yes
**Rate Limit:** `general_rate`

**Response (200):**
```json
[
  {
    "id": "uuid",
    "institution_id": "uuid",
    "name": "Personal Savings",
    "type": "savings",
    "currency": "EGP",
    "current_balance": "15000.50",
    "credit_limit": null,
    "is_dormant": false,
    "is_credit_type": false,
    "created_at": "2026-03-15T10:00:00Z"
  }
]
```

---

### POST /api/accounts
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "institution_id": "uuid",
  "name": "My Savings",
  "type": "savings|current|prepaid|cash|credit_card|credit_limit",
  "currency": "EGP|USD",
  "initial_balance": 5000.00,
  "credit_limit": 50000.00
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "institution_id": "uuid",
  "name": "My Savings",
  "type": "savings",
  "currency": "EGP",
  "current_balance": 5000.00,
  "is_credit_type": false,
  ...
}
```

**Validation:**
- Institution must belong to user
- Type must be valid
- For credit cards: credit_limit required
- Name: auto-generate if blank as `{Institution} - {Type}`

**Business Logic:**
- Sets `current_balance = initial_balance`
- For **credit cards:** balance stored as negative (debt convention)
- Currency override from account (form value ignored)

---

### GET /api/accounts/{account_id}
**Auth:** Yes
**Rate Limit:** `general_rate`

**Response (200):**
```json
{
  "account": {
    "id": "uuid",
    "name": "Credit Card",
    "type": "credit_card",
    "current_balance": -15000.00,
    "credit_limit": 50000.00,
    "is_credit_type": true,
    "currency": "EGP"
  },
  "institution_name": "HSBC",
  "billing_cycle": {
    "statement_day": 25,
    "due_day": 5,
    "days_to_statement": 5,
    "days_to_due": 12
  },
  "balance_history": [5000.00, 4950.00, ...],
  "utilization": 30.0,
  "virtual_accounts": [...],
  "transactions": [...]
}
```

---

### PUT /api/accounts/{account_id}
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "name": "Updated Name",
  "credit_limit": 50000.00,
  "is_dormant": false,
  "metadata": {...}
}
```

**Business Logic:**
- Does NOT update currency or balance
- Cannot change account type

---

### DELETE /api/accounts/{account_id}
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:** Requires confirmation
```json
{
  "confirm_name": "Account Name"
}
```

**Business Logic:**
- Soft-delete: set `is_dormant=True`
- Transactions remain in history
- Virtual accounts lose reference

---

## 3. Transactions API

### POST /api/transactions
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "type": "expense|income",
  "amount": 150.00,
  "account_id": "uuid",
  "category_id": "uuid|null",
  "note": "Lunch with team",
  "date": "2026-03-25",
  "time": "12:30:00|null",
  "tags": ["work", "lunch"],
  "virtual_account_id": "uuid|null"
}
```

**Response (200/201):**
```json
{
  "id": "uuid",
  "type": "expense",
  "amount": 150.00,
  "currency": "EGP",
  "account_id": "uuid",
  "category_id": "uuid",
  "date": "2026-03-25",
  "note": "Lunch with team",
  "balance_delta": -150.00,
  "new_balance": 5000.00,
  "created_at": "2026-03-25T12:30:00Z"
}
```

**Validation:**
- `amount > 0` (always positive; sign in balance_delta)
- `account_id` required
- `type` must be expense or income
- Date defaults to today

**Critical Business Logic:**
1. **Currency override:** Always use account's currency, never form
2. **Balance delta:**
   - Expense: `delta = -amount`
   - Income: `delta = +amount`
3. **Credit card limit check:** For credit types
   - Reject if: `new_balance < -credit_limit`
   - Available = `credit_limit + current_balance`
4. **Atomic update:** Use DB-level atomic operations
5. **VA allocation:** If provided, allocate amount to VA

**Errors:**
```json
{
  "error": "Amount must be positive",
  "field": "amount"
}
```

---

### PUT /api/transactions/{tx_id}
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "type": "expense|income",
  "amount": 200.00,
  "category_id": "uuid|null",
  "note": "Updated note",
  "date": "2026-03-25"
}
```

**Business Logic:**
- Recalculates balance_delta
- Atomically adjusts account balance by difference
- Does NOT allow changing account_id or currency

---

### DELETE /api/transactions/{tx_id}
**Auth:** Yes
**Rate Limit:** `general_rate`

**Business Logic:**
- Deletes transaction
- Atomically reverses balance impact
- Deallocates from virtual accounts

---

### GET /api/transactions
**Auth:** Yes
**Rate Limit:** `general_rate`

**Query Parameters:**
```
?account_id=uuid|
&category_id=uuid|
&type=expense|income|
&date_from=YYYY-MM-DD|
&date_to=YYYY-MM-DD|
&search=string|
&offset=0&limit=50
```

**Response (200):**
```json
{
  "transactions": [
    {
      "id": "uuid",
      "type": "expense",
      "amount": 150.00,
      "currency": "EGP",
      "account_id": "uuid",
      "account_name": "Credit Card",
      "category_id": "uuid",
      "category_name": "Food & Groceries",
      "category_icon": "🍔",
      "date": "2026-03-25",
      "note": "Lunch",
      "running_balance": 5000.00,
      "created_at": "2026-03-25T12:30:00Z"
    }
  ],
  "has_more": true,
  "next_offset": 50
}
```

**Mobile Note:** Paginate with limit=50, fetch next page as user scrolls

---

### POST /api/transactions/transfer
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "from_account_id": "uuid",
  "to_account_id": "uuid",
  "amount": 1000.00,
  "note": "Transfer to savings",
  "date": "2026-03-25"
}
```

**Response (200):**
```json
{
  "from_tx": {
    "id": "uuid1",
    "type": "transfer",
    "amount": 1000.00,
    "linked_transaction_id": "uuid2"
  },
  "to_tx": {
    "id": "uuid2",
    "type": "transfer",
    "amount": 1000.00,
    "linked_transaction_id": "uuid1"
  },
  "from_new_balance": 4000.00,
  "to_new_balance": 6000.00
}
```

**Validation:**
- Both accounts exist and belong to user
- Different accounts
- Same currency

---

### POST /api/transactions/exchange
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "from_account_id": "uuid_egp",
  "to_account_id": "uuid_usd",
  "from_amount": 10000.00,
  "fee_amount": 50.00|null,
  "fee_account_id": "uuid_cash"|null,
  "exchange_rate": 30.5,
  "date": "2026-03-25"
}
```

**Response (200):**
```json
{
  "from_tx": {...},
  "to_tx": {...},
  "fee_tx": {...}|null
}
```

**Business Logic:**
- Exchange rate stored as "EGP per 1 USD"
- Creates three transactions if fee provided (expense, income, fee)
- All atomic

---

### POST /api/transactions/batch
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "items": [
    {
      "type": "expense",
      "amount": 100.00,
      "account_id": "uuid",
      "category_id": "uuid",
      "note": "Coffee",
      "date": "2026-03-25"
    }
  ]
}
```

**Response (200):**
```json
{
  "created_count": 3,
  "failed_count": 0,
  "created": [...],
  "errors": []
}
```

**Mobile Note:** Non-atomic per item (best-effort); validate locally first

---

### POST /api/sync/transactions
**Auth:** Yes
**Rate Limit:** `api_rate`

**Request:**
```json
{
  "items": [
    {
      "type": "expense",
      "amount": 50.00,
      "account_id": "uuid",
      "category_id": "uuid",
      "note": "Offline tx",
      "date": "2026-03-25",
      "created_at": "2026-03-25T10:00:00Z"
    }
  ],
  "deleted_ids": ["uuid1", "uuid2"]
}
```

**Response (200):**
```json
{
  "created": [{"id": "uuid", ...}],
  "failed": [{"index": 0, "error": "..."}]
}
```

**Mobile Use:** Batched offline sync when online

---

## 4. Budgets API

### POST /api/budgets
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "category_id": "uuid",
  "monthly_limit": 500.00,
  "currency": "EGP"
}
```

**Response (200):**
```json
{
  "id": "uuid",
  "category_id": "uuid",
  "monthly_limit": 500.00,
  "currency": "EGP"
}
```

**Validation:**
- Category required
- Limit > 0
- Unique per (user, category, currency)

---

### GET /api/budgets
**Auth:** Yes
**Rate Limit:** `general_rate`

**Response (200):**
```json
[
  {
    "id": "uuid",
    "category_id": "uuid",
    "category_name": "Food & Groceries",
    "category_icon": "🍔",
    "monthly_limit": 500.00,
    "currency": "EGP",
    "spent": 350.00,
    "remaining": 150.00,
    "percentage": 70.0,
    "status": "amber|green|red"
  }
]
```

**Status:**
- Green: < 80%
- Amber: 80-100%
- Red: > 100%

---

### DELETE /api/budgets/{budget_id}
**Auth:** Yes
**Rate Limit:** `general_rate`

---

## 5. Categories API

### GET /api/categories
**Auth:** Yes
**Rate Limit:** `api_rate`

**Query:**
```
?type=expense|income|
```

**Response (200):**
```json
[
  {
    "id": "uuid",
    "name": "Food & Groceries",
    "type": "expense|income",
    "icon": "🍔",
    "is_system": true,
    "is_archived": false,
    "display_order": 2
  }
]
```

**Default Categories (25+):**
Household, Food & Groceries, Transport, Health, Education, Mobile, Electricity, Gas, Internet, Gifts, Entertainment, Shopping, Subscriptions, Virtual Fund, Insurance, Fees & Charges, Debt Payment, Salary, Freelance, Investment Returns, Refund, Loan Repayment Received, Travel, Cafe, Restaurant, Car, Other

---

### POST /api/categories
**Auth:** Yes
**Rate Limit:** `api_rate`

**Request:**
```json
{
  "name": "Gas Station",
  "icon": "⛽|null"
}
```

**Validation:**
- Name required, non-empty
- Defaults to type='expense'
- Prevents duplicate names

---

### PUT /api/categories/{category_id}
**Auth:** Yes
**Rate Limit:** `api_rate`

**Request:**
```json
{
  "name": "Updated Name",
  "icon": "🆕"
}
```

**Restriction:** System categories (`is_system=true`) cannot be modified

---

### DELETE /api/categories/{category_id}
**Auth:** Yes
**Rate Limit:** `api_rate`

**Business Logic:** Soft-delete (set `is_archived=True`); existing transactions keep category reference

---

## 6. People API (Loans & Debt)

### POST /api/people
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "name": "Ahmed"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "name": "Ahmed",
  "net_balance_egp": 0.00,
  "net_balance_usd": 0.00
}
```

---

### POST /api/people/{person_id}/loan
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "amount": 500.00,
  "account_id": "uuid",
  "loan_type": "loan_out|loan_in",
  "note": "Money for trip"
}
```

**Response (200):**
```json
{
  "id": "uuid",
  "type": "loan_out|loan_in",
  "amount": 500.00,
  "currency": "EGP",
  "note": "Money for trip"
}
```

**Business Logic:**
- `loan_out`: you lent money (person owes you)
- `loan_in`: you borrowed (you owe person)
- Currency from account (override rule applies)
- Atomically updates account balance and person net balance

---

### POST /api/people/{person_id}/repay
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "amount": 250.00,
  "account_id": "uuid"
}
```

**Business Logic:** Creates offsetting transaction, reduces debt

---

### GET /api/people/{person_id}
**Auth:** Yes
**Rate Limit:** `general_rate`

**Response (200):**
```json
{
  "person": {
    "id": "uuid",
    "name": "Ahmed",
    "net_balance_egp": 250.00,
    "net_balance_usd": 0.00
  },
  "transactions": [...]
}
```

---

## 7. Virtual Accounts API

### POST /api/virtual-accounts
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "name": "Vacation Fund",
  "target_amount": 5000.00|null,
  "icon": "✈️",
  "color": "#FF6B6B",
  "account_id": "uuid|null",
  "exclude_from_net_worth": false
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "name": "Vacation Fund",
  "target_amount": 5000.00,
  "current_balance": 0.00,
  "progress_percentage": 0.0
}
```

---

### GET /api/virtual-accounts
**Auth:** Yes
**Rate Limit:** `general_rate`

**Response (200):**
```json
{
  "accounts": [
    {
      "id": "uuid",
      "name": "Vacation Fund",
      "target_amount": 5000.00,
      "current_balance": 1500.00,
      "progress_percentage": 30.0,
      "icon": "✈️"
    }
  ],
  "warnings": [
    "Total virtual account allocations exceed account balance"
  ]
}
```

---

### GET /api/virtual-accounts/{va_id}
**Auth:** Yes
**Rate Limit:** `general_rate`

**Response (200):**
```json
{
  "account": {...},
  "transactions": [...],
  "allocations": [...],
  "over_allocated": false
}
```

---

## 8. Recurring Rules API

### POST /api/recurring
**Auth:** Yes
**Rate Limit:** `general_rate`

**Request:**
```json
{
  "type": "expense|income",
  "amount": 100.00,
  "account_id": "uuid",
  "category_id": "uuid|null",
  "note": "Netflix subscription",
  "frequency": "monthly|weekly",
  "next_due_date": "2026-04-01",
  "auto_confirm": false
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "type": "expense",
  "amount": 100.00,
  "frequency": "monthly",
  "next_due_date": "2026-04-01",
  "auto_confirm": false,
  "is_active": true
}
```

---

### GET /api/recurring
**Auth:** Yes
**Rate Limit:** `general_rate`

**Response (200):**
```json
{
  "pending_rules": [
    {
      "id": "uuid",
      "type": "expense",
      "amount": 50.00,
      "note": "Gym membership",
      "due_date": "2026-03-25"
    }
  ]
}
```

---

### POST /api/recurring/{rule_id}/confirm
**Auth:** Yes
**Rate Limit:** `general_rate`

**Business Logic:**
- Creates transaction from template
- Updates rule's `next_due_date` based on frequency

---

### POST /api/recurring/{rule_id}/skip
**Auth:** Yes
**Rate Limit:** `general_rate`

**Business Logic:** Updates `next_due_date`, marks as pending for next cycle

---

## 9. Reports API

### GET /api/reports
**Auth:** Yes
**Rate Limit:** `general_rate`

**Query:**
```
?year=2026&month=3&currency=EGP|USD|&account_id=uuid|
```

**Response (200):**
```json
{
  "year": 2026,
  "month": 3,
  "period": "March 2026",
  "spending_by_category": [
    {
      "category_id": "uuid",
      "category_name": "Food & Groceries",
      "category_icon": "🍔",
      "amount": 1500.00,
      "percentage": 35.0
    }
  ],
  "income_vs_expenses": {
    "income": 10000.00,
    "expenses": 4200.00,
    "net": 5800.00
  }
}
```

---

## 10. Dashboard API

### GET /api/dashboard
**Auth:** Yes
**Rate Limit:** `general_rate`

**Response (200):**
```json
{
  "net_worth": {
    "total": 85000.00,
    "by_currency": {
      "EGP": 75000.00,
      "USD": 10000.00
    }
  },
  "sparkline": [50000, 52000, 54500, ...],
  "recent_transactions": [...],
  "budgets": [...],
  "credit_cards": [...],
  "health_warnings": []
}
```

---

## Common Patterns

### Response Headers
```
Content-Type: application/json
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1234567890
```

### Error Responses
```json
{
  "error": "Human-readable error message",
  "field": "field_name|null",
  "code": "ERROR_CODE|null"
}
```

### HTTP Status Codes
- `200` - Success
- `201` - Created
- `204` - No Content
- `400` - Bad Request (validation error)
- `401` - Unauthorized (no session)
- `404` - Not Found
- `409` - Conflict (e.g., duplicate budget)
- `429` - Rate Limited
- `500` - Server Error

### Rate Limiting
- `login_rate`: Auth endpoints (5 req/min per IP)
- `general_rate`: Most endpoints (120 req/min per user)
- `api_rate`: JSON endpoints (60 req/min per user)

### Mobile Considerations
- **Session Management:** Store Bearer token in Keychain/Keystore, include in Authorization header
- **Offline Sync:** Use `/api/sync/transactions` for batched offline changes
- **Pagination:** Default limit=50, include `has_more` + `next_offset`
- **Error Handling:** Always parse error JSON, show field-specific messages
- **Timeout:** Set 30-second timeout on all requests

---

**Generated from production Django backend on 2026-03-25**
