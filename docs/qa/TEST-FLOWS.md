# Test Flows — ClearMoney Feature Coverage

> Reference document (not a rule). Detailed test scenarios for all 14 feature areas.
> Use this when writing new tests or planning manual QA. For each feature:
> - Preconditions needed
> - Test scenarios (happy path + error paths + edge cases)
> - Expected results
> - Layer recommendation (unit / e2e / both)
> - Known gaps marked with `GAP:`
>
> For E2E selectors and patterns, see `e2e/tests/*.py` files.
> For service-level test patterns, see `backend/*/tests/test_services.py`.

---

## 1. Authentication

### 1.1 Magic Link Login

**Layer:** E2E (security-critical — session cookie behavior must be tested in browser)

**Preconditions:** Existing user in DB

**Scenarios:**

**A. Valid email → "Check your email" page shown**
- User submits valid email on `/login`
- Timing < 2s → rejected ("too fast" anti-bot)
- Timing > 2s → accepted
- "Check your email" page shown (never reveals if email exists)
- Email sent via Resend (or logged to stdout in dev mode)

**B. Valid token → redirected to /, session cookie set**
- GET `/auth/verify?token=<valid_token>`
- HTTP 302 redirect to `/`
- `clearmoney_session` cookie set in browser
- Session row exists in `sessions` table
- User can navigate to protected routes

**C. Expired token (TTL 15 min) → "Link expired"**
- GET `/auth/verify?token=<expired_token>`
- HTTP 200, page shows "Link expired, request a new link"
- No session created

**D. Used token (already verified) → "Link expired"**
- Token used once → `used=True` set in DB
- Second attempt with same token → "Link expired"

**E. Honeypot filled → request rejected**
- Form includes hidden "website" field (honeypot)
- If filled → request silently rejected (HTTP 400 or silent redirect)

**F. Empty email → validation error, stays on /login**
- Submit form with blank email
- Validation error shown in form
- No email sent

**Regression guard:** [CP-1: Authentication](../critical-paths.md#cp-1-authentication--magic-link-login)

---

### 1.2 Registration

**Layer:** E2E

**Preconditions:** Email not in DB, Resend API key configured (or dev mode)

**Scenarios:**

**A. New email → "Welcome to ClearMoney" page**
- User submits new email on `/register`
- Email not in `users` table
- Magic link email sent (or logged to stdout)
- "Check your email" page shown

**B. Token verify for registration → redirects to /, 27 categories seeded**
- GET `/auth/verify?token=<registration_token>`
- HTTP 302 redirect to `/`
- User row created in `users` table
- 27 default categories created for user in `categories` table
- User is authenticated (session cookie set)

**C. Already registered email → "Check your email" (not "already registered")**
- Submit already-registered email on `/register`
- Same "Check your email" response (privacy — never reveal email exists)
- Email sent to existing user (magic link to login, not register)

---

### 1.3 Logout

**Layer:** E2E

**Scenarios:**

**A. POST /logout → session deleted from DB, cookie cleared, redirect to /login**
- Authenticated user clicks logout button
- HTTP 302 redirect to `/login`
- Session row deleted from `sessions` table
- Cookie `clearmoney_session` cleared

**B. After logout, navigating to / → redirect to /login**
- Session deleted, old cookie invalid
- GET `/` → HTTP 302 to `/login`

**C. Stale cookie → redirect to /login (GoSessionAuthMiddleware handles)**
- Old/invalid cookie in request
- GoSessionAuthMiddleware looks up session → not found
- HTTP 302 redirect to `/login`

---

## 2. Dashboard

### 2.1 Dashboard Render

**Layer:** E2E

**Preconditions:** Authenticated user with: institution, account (10,000 EGP), 1 expense transaction

**Scenarios:**

**A. GET / → 200, all panels visible (net worth, summary cards, accounts)**
- Page loads without 500 error
- "Net Worth" section present with amount
- Summary cards: "Liquid Cash", "Credit Used", "Credit Available"
- Recent transactions list shows latest 5 transactions

**B. Empty state (no accounts) → "Add your first account" CTA visible**
- Authenticated user with no accounts
- Dashboard shows empty state message
- CTA button "Add your first account" links to `/accounts/new`

**C. With transactions → recent transactions list shows latest 5**
- Dashboard shows transaction note, amount, date
- If > 5 transactions, shows only latest 5
- Can click transaction to view detail

**D. With budgets → budget progress bars visible**
- If user has budgets, dashboard "Budgets" section shows progress bars
- Each budget shows: category name, used/limit amounts, progress bar percentage
- Amber/red indicator if budget > 80% or > 100%

**E. With people (loans) → people summary section visible**
- If user has recorded loans/borrows, "People" section shows summary
- Shows payoff projection if applicable

**F. With virtual accounts → VA progress bars in dashboard**
- If user has VA, dashboard "Virtual Accounts" section shows progress
- Shows current/target amounts

**Expected results:**
- Net worth = sum of all account balances in EGP equivalent
- Liquid Cash = sum of non-CC account balances (CC balances negative, stored as debt)
- Credit Used = sum of CC balances (displayed positive, stored negative)
- No 500 errors, no JS console errors (check DevTools)

---

### 2.2 Dashboard HTMX Partials

**Layer:** Unit (view tests) + E2E (if triggered by user interaction)

**Scenarios:**

**A. GET /dashboard/partials/budgets → returns budget HTML fragment (200)**
- Request is HTMX partial request
- Response is HTML fragment (no DOCTYPE, no base layout)
- No auth → 302 to /login

**B. GET /dashboard/partials/health → returns health warnings fragment**
- If account is dormant/at risk, warning shown
- If no warnings, empty/minimal fragment returned

**C. GET /dashboard/partials/virtual-accounts → returns VA summary fragment**
- If no VAs, empty fragment
- If VAs exist, progress bars shown

**D. All partials: unauthenticated → 302 to /login**
- No bypass for partial requests
- Auth middleware applies to all views

---

## 3. Accounts

### 3.1 Create Account (HTMX Bottom Sheet)

**Layer:** Both (unit for validation, E2E for bottom sheet HTMX flow)

**Preconditions:** Authenticated user, institution created (or preset institution selected)

**Scenarios:**

**A. Create current account (EGP, 10,000 initial balance) → account appears in list**
- Form fields: name, institution, currency, initial balance, account type
- Defaults: type = current, currency = EGP
- POST `/accounts` with valid data
- HTTP 302 or HTMX 200 response (bottom sheet closes)
- Account appears in `/accounts` list with correct balance

**B. Create CC account (EGP, credit limit 5,000) → CC-specific fields present**
- Select account type "Credit Card"
- CC-specific fields appear: billing_cycle_day, credit_limit, interest_rate
- POST creates CC account with `current_balance = 0` (no debt yet)

**C. Create with institution preset → icon + color populated**
- Select "Egypt National Bank" from institution list
- Icon and color auto-populated from preset

**D. Create dormant account → excluded from dashboard liquid cash**
- Toggle "Dormant" checkbox
- Account created with `dormant = True`
- Account hidden from dashboard liquid cash calculation
- But still visible in account list with "Dormant" badge

**E. Missing required fields (name, institution) → 400 error**
- Submit form with blank name
- Validation error shown in form: "Name is required"
- No account created

**F. Negative initial balance → accepted (represents debt)**
- Submit balance = -5000
- Service accepts it (edge case: user recording existing debt)
- Account created with negative balance

**Balance rules:**
- Non-CC: `current_balance = initial_balance` at creation
- CC: `current_balance = 0` at creation (credit limit is separate)

**Isolation test pattern:**
```python
def test_cannot_access_other_users_account(self, ...):
    account_b = AccountFactory(user_id=other_user.id)
    response = client.get(f'/accounts/{account_b.id}')
    assert response.status_code == 404
```

---

### 3.2 Edit Account (HTMX Bottom Sheet)

**Layer:** Unit (for data changes), E2E (for bottom sheet open/close behavior)

**Scenarios:**

**A. Edit account name → updated in DB and in list**
- Click edit button on account row
- Bottom sheet opens with form
- Change name from "Checking" to "Primary"
- POST `/accounts/<id>` with new data
- Account list updates immediately (HTMX swap)

**B. Edit CC billing cycle → due date recalculates**
- CC account, change billing_cycle_day from 15 to 1st
- Next statement date recalculates
- Dashboard CC payment guidance updated

**C. Toggle dormant → account hidden/shown in dropdowns**
- Toggle "Dormant" checkbox
- Account removed from transaction account dropdown
- Account still visible in account list with "Dormant" label

**D. Delete with name confirmation → account removed, balance zeroed in net worth**
- Delete button opens confirmation dialog
- Dialog requires typing account name to confirm
- POST `/accounts/<id>/delete`
- Account deleted from DB (cascade: transactions/budgets updated)
- Net worth recalculates immediately

---

### 3.3 Account Balance Sparkline

**Layer:** Unit (service) + E2E (visual verification)

**Scenarios:**

**A. Account with no snapshots → sparkline renders empty (no 500)**
- New account, no daily snapshots yet
- Sparkline element renders but empty (no data)
- No 500 error

**B. Account with 7 snapshots → sparkline shows correct trend**
- Account has 7 `AccountSnapshot` rows (one per day)
- Sparkline (SVG polyline) shows trend
- Visual verification: line goes up/down correctly

---

## 4. Transactions

### 4.1 Create Transaction (New Form)

**Layer:** Both (unit for validation + balance updates, E2E for UI flow)

**Preconditions:** Authenticated user, account (EGP, 10,000)

**Scenarios:**

**A. Create expense (500 EGP) → balance = 9,500, "Transaction saved!" shown**
- Form: amount, type, category, note, date (defaulted to today)
- POST `/transactions`
- "Transaction saved!" message in `#transaction-result` (HTMX swap)
- Account balance updates in UI → 9,500
- Balance in DB: `SELECT current_balance FROM accounts` = 9500.00 (NUMERIC, exact)

**B. Create income (2,000 EGP) → balance = 12,000**
- Same flow, type = income
- Balance increases

**C. Category auto-suggests based on note (smart defaults)**
- Type note "Coffee Cafe"
- Category field auto-suggests "Food" or "Dining"
- User can override

**D. Future date → rejected (max="{{ today }}" on date input)**
- Try to set date = tomorrow
- HTML `max` attribute prevents selection
- Or if date input allows: POST rejected with "Date cannot be in future"

**E. Zero amount → rejected (service ValueError → 400)**
- amount = 0
- POST returns 400 with error: "Amount must be greater than 0"

**F. Negative amount → rejected**
- amount = -500
- Service validation rejects negative amounts

**G. Form currency overridden by account currency (common-pitfall rule)**
- Account is EGP
- Form's currency field (if present) is ignored
- Service enforces `tx.currency = account.currency`
- Test: assert `tx["currency"] == "EGP"` regardless of form input

---

### 4.2 Quick Entry (Bottom Sheet)

**Layer:** Unit (form rendering + service), E2E (HTMX submit + success animation)

**Preconditions:** Account exists, user on dashboard

**Scenarios:**

**A. Submit quick entry → transaction created, success screen shown, balance updates**
- Click "Quick Entry" button
- Bottom sheet opens with minimal form (amount, category, note)
- Fill amount = 350, category = "Food"
- Click Submit
- Transaction created, success animation shown
- Sheet closes
- Dashboard balance updates immediately

**B. Draft persistence: form data saved on input, restored on re-open**
- Open quick entry, fill amount = 250
- Switch to another sheet (budgets)
- Re-open quick entry
- Form still shows amount = 250 (draft restored from localStorage)

**C. Draft cleared on success**
- Submit quick entry → success
- Sheet closes
- Re-open quick entry → form is blank (draft cleared)

**D. Tab switch (expense/income) → persisted in draft**
- Open quick entry, tab to "Income"
- Fill amount = 500
- Switch tabs back to "Expense"
- Switch back to "Income" → amount still 500

---

### 4.3 Batch Entry

**Layer:** Unit (form rendering + service atomicity), E2E (add/remove rows, submit all)

**Preconditions:** Account exists, user navigates to `/batch-entry`

**Scenarios:**

**A. Add row → new row cloned with today's date, blank inputs**
- Click "Add Row" button
- New row appears below existing rows
- Date defaulted to today
- Amount, category, note fields blank

**B. Remove row → row removed**
- Click "Remove" button on a row
- Row disappears from form

**C. Submit 3 rows → 3 transactions created, all balances updated**
- Fill 3 rows with amounts: 100, 200, 50 (total 350)
- POST `/transactions/batch`
- All 3 transactions created in DB
- Final balance = starting - 350
- Success message shows "3 transactions created"

**D. One invalid row → all-or-nothing? (service atomicity)**
- Fill 3 rows: valid, valid, zero-amount (invalid)
- POST → service returns 400 (validation error)
- NO transactions created (atomic transaction rolls back)

**E. Empty row (missing required field) → validation error**
- Add row, leave amount blank
- Submit → validation error, form stays open

**GAP:** No E2E test for batch submit success yet. Add to `e2e/tests/test_transactions.py` with class `TestBatchEntry`.

---

### 4.4 Transfer

**Layer:** Both (service critical, E2E for UI flow)

**Preconditions:** Two EGP accounts (Source: 10,000, Dest: 0)

**Scenarios:**

**A. EGP→EGP transfer: source −5,000, destination +5,000, net worth unchanged**
- Fill: amount = 5,000, source account, destination account
- POST `/transactions/transfer`
- Source account balance = 5,000 (10,000 - 5,000)
- Destination account balance = 5,000 (0 + 5,000)
- Net worth = 10,000 (unchanged)
- Two transaction rows created (one per account)

**B. With InstaPay fee: source −5,050 (fee shown as separate tx), dest +5,000**
- Same flow, enable "InstaPay" option
- Source deducted by amount + fee (5,050)
- Destination receives amount only (5,000)
- Fee difference (50) shown in separate transaction row or note

**C. Note added to transfer → appears in transaction list**
- Add note "Rent payment to savings"
- Note visible in both accounts' transaction lists

**D. Same source = destination → rejected (400)**
- Both dropdowns select same account
- Submit → validation error: "Cannot transfer to same account"

**E. Different currencies → rejected (use exchange instead)**
- Source = EGP account, destination = USD account
- Submit → error: "Use exchange for different currencies"

---

### 4.5 Exchange (Currency Conversion)

**Layer:** Both (service critical, E2E for UI flow)

**Preconditions:** EGP account (20,000), USD account (0), exchange rate available

**Scenarios:**

**A. EGP→USD at rate 50: EGP −5,000, USD +100.00 (JS auto-calculates counter)**
- Fill: amount_from = 5,000 (EGP), amount_to = auto-calc
- Rate = 50 (form field or auto-lookup)
- JS calculates: 5,000 / 50 = 100 USD
- Submit → EGP balance -= 5,000, USD balance += 100

**B. USD→EGP at rate 50: USD −100, EGP +5,000 (rate inverted)**
- amount_from = 100 (USD), rate = 50
- JS calculates: 100 * 50 = 5,000 EGP
- Submit → USD -= 100, EGP += 5,000

**C. Missing rate → rejected (required field)**
- Leave rate blank
- Validation error: "Rate is required"

**D. Same currency → rejected**
- Source = USD, destination = USD
- Error: "Cannot exchange same currency"

**E. ExchangeRateLog entry created for each exchange**
- Exchange completed
- `ExchangeRateLog` row created (for historical tracking)
- Rate and currencies logged

**GAP:** E2E test for exchange with balance verification not yet written. Add to `test_transactions.py`.

---

### 4.6 Search and Filtering

**Layer:** Unit (service filter logic), E2E (UI debounce + filter select)

**Preconditions:** Account with 10+ transactions across categories and types

**Scenarios:**

**A. Search by note: "Coffee" → only Coffee transactions shown (300ms debounce)**
- Type "Coffee" in search box
- Results filtered after 300ms debounce
- Only transactions with "Coffee" in note shown
- Counts update (e.g., "3 transactions")

**B. Filter by type: "expense" → only expense transactions shown**
- Click type filter dropdown
- Select "Expense"
- List shows only expense transactions
- Income/transfer transactions hidden

**C. Filter by date range → transactions in range only**
- Select date_from = start of month, date_to = end of month
- List shows only transactions in range

**D. Combined search + type filter → correctly intersected**
- Search "Coffee" AND filter type = "expense"
- Only expense transactions with "Coffee" in note shown

**E. Clear filter → all transactions shown**
- Click "Clear filters" button
- Search box cleared, type filter reset
- All transactions shown

---

### 4.7 Swipe to Delete

**Layer:** E2E (gesture must be tested in browser)

**Preconditions:** Transaction in list view

**Scenarios:**

**A. Swipe left → delete button appears**
- Touch/mouse drag left on transaction row
- Delete button reveals

**B. Click delete → transaction removed, balance restored**
- Click revealed delete button
- Confirmation dialog (optional)
- POST `/transactions/<id>/delete`
- Transaction removed from DB
- Balance updated in UI

**C. Keyboard alternative: delete button accessible without gesture**
- Tab to delete button (keyboard nav)
- Press Enter to delete
- Or always show delete button, not just on swipe

**GAP:** E2E swipe test exists but only verifies row is visible post-delete, not full flow (delete → DB verified, balance updated). Enhance test coverage.

---

### 4.8 Transaction Detail

**Layer:** Unit + E2E

**Preconditions:** Transaction exists in DB

**Scenarios:**

**A. GET /transactions/<id> → detail sheet renders**
- All transaction fields shown: amount, category, note, date, type
- Edit button, delete button visible

**B. Other user's transaction → 404**
- User A tries to access User B's transaction
- HTTP 404 response

**C. Edit button → edit form loads**
- Click edit
- Form pre-filled with transaction data
- Amount, category, note, date all editable
- Submit updates transaction

**D. Delete → confirmation, transaction removed**
- Click delete
- Confirmation: "Are you sure?"
- POST `/transactions/<id>/delete`
- Transaction removed

**E. Balance impact shown**
- Detail shows account balance before/after transaction
- Or shows impact: "Reduced balance by 500"

---

## 5. Reports

### 5.1 Monthly Spending Report (Donut Chart)

**Layer:** Unit (service: correct category totals), E2E (page renders, not 500)

**Preconditions:** Account with expenses in current month

**Scenarios:**

**A. No transactions this month → empty state shown**
- Month with zero transactions
- Donut chart not rendered (or empty)
- "No spending this month" message shown

**B. With expenses → donut chart rendered (CSS conic-gradient, no JS)**
- Expenses across 3 categories: Food (500), Transport (300), Entertainment (200)
- Donut chart shows 3 slices with proportional arc lengths
- Colors from palette (8 colors, cycles if >8 categories)
- Legend shows category names + amounts + percentages

**C. Filter by currency → only EGP or USD transactions shown**
- Multi-currency accounts: 500 EGP (Food) + 100 USD (Food)
- Filter "EGP" → chart shows only EGP transactions
- EGP total = 500, USD filter shows only USD transactions

**D. Navigate months → correct month's data loaded**
- Select previous month dropdown
- Report recalculates with correct month's data
- Navigation via prev/next buttons or month selector

**E. Income transactions excluded from expense donut**
- Month has: 500 EGP expense, 1000 EGP income
- Donut chart shows ONLY 500 (expense)
- Income excluded from this report

**Expected results:**
- Chart renders without JS errors
- All slices sum to 100%
- Legend percentages accurate
- No negative values
- No 500 errors

---

### 5.2 6-Month Bar Chart (Income vs Expense)

**Layer:** Unit (service: correct income/expense totals per month)

**Preconditions:** Transactions across last 6 months

**Scenarios:**

**A. No transactions → 6 empty bars shown**
- No expense/income data for 6-month period
- 6 month labels shown (e.g., "Sep", "Oct", ...)
- Bar heights = 0

**B. With data → bar heights proportional to amounts**
- Month 1: 1,000 EGP expense, 2,500 EGP income → bars shown
- Month 2: 500 EGP expense, 1,000 EGP income → shorter bars
- Bar heights visually proportional

**C. Current month highlighted**
- Current month bar (e.g., March) has different color/style
- Or marker/bold label

**D. Year boundary (Jan → Dec of previous year)**
- 6-month period crosses Jan 1
- Previous year's Dec shown alongside current year's Jan-May
- Months labeled correctly

**E. Legend/legend shows income (green?) vs expense (red?) colors**
- Two legend entries: "Income", "Expense"
- Bars color-coded accordingly

---

## 6. Credit Cards

### 6.1 Statement View

**Layer:** Unit (service calculations)

**Preconditions:** CC account with transactions, billing_cycle_day set

**Scenarios:**

**A. Statement shows transactions since statement_day**
- CC billing cycle day = 15
- Transaction on 10th → NOT in current statement (previous)
- Transaction on 16th → in current statement
- Statement shows: start_date = last statement_day, end_date = today

**B. Interest-free period days remaining calculated correctly**
- CC config: 45-day interest-free period
- Statement generated on day 15 (billing day)
- Days remaining = 45 - (today - 15)
- Countdown shown in UI

**C. Minimum payment guidance shown when balance > 0**
- CC balance = 2,500
- Minimum payment = balance * 0.05 (5% rule, or config-based)
- "Minimum payment due: 125" shown

**D. Utilization donut chart: 60% usage → 60% arc**
- Credit limit = 5,000
- Current balance (debt) = 3,000 (stored negative)
- Utilization = 3,000 / 5,000 = 60%
- Donut shows 60% arc (240°)

---

## 7. People (Loans)

### 7.1 Loan Lifecycle

**Layer:** Both (service logic + E2E for UI flow)

**Preconditions:** Person created, account with EGP

**Scenarios:**

**A. Add person → person in list**
- POST `/people` with name = "Ahmed"
- Person appears in `/people` list with zero balance

**B. Record "I lent" → account balance decreases, person shows positive balance**
- Create transaction: type = "lent", person = Ahmed, amount = 500
- Current account balance -= 500
- Ahmed's balance in people list = +500 (Ahmed owes me)

**C. Record "I borrowed" → account balance increases, person shows negative balance**
- Create transaction: type = "borrowed", person = Ahmed, amount = 300
- Current account balance += 300
- Ahmed's balance = -300 (I owe Ahmed)

**D. Record repayment → person balance decreases toward zero**
- Ahmed owes 500, I record: "Ahmed repaid 200"
- Ahmed's balance = 500 - 200 = 300

**E. Over-repay (positive) → balance flips to negative (borrowed more)**
- Ahmed owes 500, I record: "Ahmed repaid 600"
- Ahmed's balance = 500 - 600 = -100 (I owe Ahmed 100)

**F. Full lifecycle: lend → repay → balance = 0**
- Lend 500 → Ahmed owes 500
- Repay 500 → Ahmed owes 0
- No balance shown in list (zero state)

---

### 7.2 Payoff Projection

**Layer:** Unit (service calculation)

**Preconditions:** Person with positive balance, repayment plan set

**Scenarios:**

**A. Person with positive balance + monthly repayment plan → months to payoff shown**
- Ahmed owes 500, monthly repayment = 100
- Projection: 500 / 100 = 5 months
- UI shows "Payoff in 5 months" or countdown

**B. Zero balance → "No debt" state shown**
- Ahmed's balance = 0
- List shows "No active balance" or similar

---

## 8. Virtual Accounts (Envelope Budgeting)

### 8.1 VA Lifecycle

**Layer:** Both (unit for service, E2E for UI)

**Preconditions:** Main account exists

**Scenarios:**

**A. Create VA (Emergency Fund, target 50,000) → appears in list**
- POST `/virtual-accounts` with name, target balance
- VA appears in list with progress: 0 / 50,000 (0%)

**B. Contribute 1,000 → VA balance = 1,000, progress 2%**
- POST `/virtual-accounts/<id>/contribute` with amount = 1,000
- VA balance = 1,000
- Progress = 1,000 / 50,000 = 2%

**C. Withdraw 500 → VA balance = 500**
- POST `/virtual-accounts/<id>/withdraw` with amount = 500
- VA balance = 1,000 - 500 = 500

**D. Allocate transaction to VA → VA balance updates, transaction linked**
- Create transaction (or edit existing), assign to VA
- Transaction.virtual_account_id set
- VA balance updated

**E. Archive VA → removed from list, excluded from dashboard**
- Click archive button
- VA hidden from active list
- VA excluded from dashboard summary

**F. Edit VA name/target → updated in list**
- Edit VA: change name from "Emergency Fund" to "Emergency Reserve"
- Change target from 50,000 to 75,000
- List updates immediately

---

## 9. Budgets

### 9.1 Budget Lifecycle

**Layer:** Both (unit for validation + balance updates, E2E for UI)

**Preconditions:** Account, expense categories

**Scenarios:**

**A. Create budget (Food, 2,000 EGP) → appears in list with 0/2,000**
- POST `/budgets` with category, currency, limit
- Budget appears in `/budgets` list
- Status: "0 spent, 2,000 limit, 2,000 remaining" (green)

**B. Add 500 EGP Food expense → budget shows 500/2,000 (25%), "1,500 remaining"**
- Create transaction: Food category, 500 EGP
- Budget recalculates: spent = 500, remaining = 1,500
- Progress bar: 25% filled

**C. Add 1,600 more → 2,100/2,000, "Over budget by 100" (red)**
- Add another 1,600 Food expense
- Total spent = 2,100 (exceeds 2,000 limit)
- Status shows: "Over by 100" (red alert)
- Progress bar shows 105% (visually overfilled)

**D. Amber threshold (80%): 1,600/2,000 → amber color**
- Budget at 80% (1,600 of 2,000 spent)
- Progress bar changes to amber (warning)
- Text: "Approaching limit" or similar

**E. Duplicate (same category + currency) → rejected**
- Try to create second Food/EGP budget
- 400 error: "Budget already exists for Food in EGP"

**F. Delete budget → removed from list and dashboard**
- Click delete on budget row
- Confirmation dialog
- Budget deleted
- Dashboard budget section updates (budget removed)

**Expected results:**
- Budget calculations exact (Decimal precision)
- Progress bars accurate percentages
- Color indicators (green/amber/red) correct
- Dashboard panel reflects same data as `/budgets` page

---

## 10. Recurring

### 10.1 Recurring Rules

**Layer:** Unit (service-level, background job processing)

**Preconditions:** Account exists

**Scenarios:**

**A. Create weekly rule → next_due = today + 7 days**
- POST `/recurring/rules` with frequency = "weekly", category = "Food", amount = 100
- Rule created with next_due = today + 7 days
- Rule appears in `/recurring/rules` list

**B. Create monthly rule → next_due = same day next month (clamped if overflow)**
- Frequency = "monthly", next_due = "15th of month"
- If current month is Jan 31, next_due clamped to Feb 28 (not valid date)
- Rule created correctly

**C. Process recurring: due rule → transaction created, due date advanced**
- Background job runs (manage.py process_recurring or startup_jobs)
- Rules with next_due <= today processed
- Transaction created for each
- next_due advanced (today + frequency)

**D. Auto-confirm rule → transaction created without user action**
- Rule has auto_confirm = True
- Background job creates transaction
- No user intervention needed

**E. Skip rule → due date advances, no transaction**
- User clicks "Skip" on rule in list
- Transaction NOT created
- next_due advanced

**F. Delete rule → removed from list**
- Click delete
- Rule removed, no more transactions created

---

## 11. Investments

### 11.1 Investment Portfolio

**Layer:** Unit (service-level valuation calculations)

**Preconditions:** Account created

**Scenarios:**

**A. Create investment (Fund A, 100 units, 50 EGP/unit) → valuation = 5,000**
- POST `/investments` with name, units, unit_price
- Investment created
- Valuation = 100 * 50 = 5,000 EGP

**B. Update unit price (55 EGP) → valuation = 5,500**
- PATCH `/investments/<id>` with unit_price = 55
- Valuation recalculates: 100 * 55 = 5,500 EGP
- Gain/loss shown: 5,500 - 5,000 = +500

**C. Delete investment → removed from portfolio**
- DELETE `/investments/<id>`
- Investment removed
- Portfolio total recalculates

**D. Portfolio total = sum of all valuations**
- Fund A = 5,500, Fund B = 3,000
- Portfolio total = 8,500

---

## 12. Settings

### 12.1 CSV Export

**Layer:** Unit (view returns CSV content-type)

**Preconditions:** Authenticated user with transactions

**Scenarios:**

**A. GET /settings/export/transactions → CSV file downloaded**
- Click "Export as CSV"
- Browser downloads `transactions.csv`
- Content-Type = `text/csv`

**B. CSV contains user's transactions only (isolation)**
- User A exports CSV
- CSV contains only User A's transactions
- No User B data present

**C. Empty database → empty CSV (header row only)**
- User with no transactions exports
- CSV contains header row (columns) only, no data rows

---

### 12.2 Dark Mode

**Layer:** E2E (class toggle on `<html>`, persistence)

**Preconditions:** Authenticated user

**Scenarios:**

**A. Toggle dark mode → `<html>` class="dark", persisted in localStorage**
- Click dark mode toggle button
- `<html>` element class toggles (add/remove "dark")
- localStorage["theme"] = "dark" (or "light")

**B. Page reload → dark mode preference preserved**
- Set dark mode ON
- Refresh page
- Dark mode persists (read from localStorage on init)

**C. Dark mode: all panels readable (contrast tested separately)**
- Text on background: contrast >= 4.5:1 (tested in accessibility audit)
- See `.claude/rules/accessibility-qa-protocol.md` for contrast verification

---

### 12.3 Push Notifications

**Layer:** Unit (model/service for subscription management)

**Scenarios:**

**A. Subscribe → endpoint + keys stored in DB**
- Service worker registration
- User clicks "Enable notifications"
- POST `/settings/push/subscribe` with endpoint + P256dh/auth keys
- Subscription row created in `subscriptions` table

**B. Unsubscribe → subscription deleted**
- User clicks "Disable notifications"
- POST `/settings/push/unsubscribe`
- Subscription deleted from DB

---

## 13. PWA (Progressive Web App)

### 13.1 Installability

**Layer:** E2E (service worker registration, manifest)

**Preconditions:** User on mobile device or emulated mobile

**Scenarios:**

**A. Service worker registered → /static/sw.js loads (200)**
- Open DevTools, Applications tab
- Service worker listed and active
- HTTP GET `/static/sw.js` returns 200

**B. Manifest present → /manifest.json returns correct content-type**
- HTTP GET `/manifest.json`
- Content-Type = `application/manifest+json`
- JSON contains: name, icons, theme_color, etc.

**C. Icons referenced in manifest exist**
- Manifest references icon URLs
- Icons accessible at those URLs
- No 404 responses

**D. App installable prompt shown on supported browsers**
- User on Chrome mobile
- "Add to Home Screen" prompt appears
- Install button clickable

---

## 14. Data Isolation (Cross-Cutting)

This applies to **every feature**. Always verify user data isolation.

### 14.1 Pattern to Apply

For each new resource type (Account, Transaction, Budget, etc.), add to `backend/<app>/tests/test_views.py`:

```python
class TestIsolation:
    def test_cannot_access_other_users_<resource>(self, auth_client, db):
        """Verify user_a cannot access user_b's resource."""
        resource_b = <ResourceFactory>(user_id=other_user.id)
        response = auth_client.get(f'/<resource>/{resource_b.id}')
        assert response.status_code == 404

    def test_list_excludes_other_users_<resource>(self, auth_client, db):
        """Verify user_a's list doesn't include user_b's resources."""
        resource_b = <ResourceFactory>(user_id=other_user.id)
        response = auth_client.get('/<resource>/')
        assert resource_b.id not in response.content.decode()
```

### 14.2 Service-Level Isolation

Every service method that filters by user must have a test:

```python
def test_list_filtered_by_user(self, db):
    """Verify service returns only user_a's resources."""
    user_a = UserFactory()
    user_b = UserFactory()
    ResourceFactory.create_batch(3, user_id=user_a.id)
    ResourceFactory.create_batch(2, user_id=user_b.id)

    results = service.list_for_user(user_a.id)
    assert len(results) == 3
    assert all(r.user_id == user_a.id for r in results)
```

---

## Known Gaps (Feature Coverage)

| Feature | Gap | Recommendation |
|---------|-----|-----------------|
| Batch Entry | No E2E test for submit success | Add `TestBatchEntry::test_create_3_transactions` |
| Transfer | E2E covers happy path, missing error cases | Add error scenarios (same account, currency mismatch) |
| Exchange | No E2E for currency validation or balance verification | Add `test_exchange_updates_both_balances`, `test_different_currencies_rejected` |
| Search/Filter | No E2E for combined filters | Add `test_search_and_type_filter_combined` |
| Swipe-to-Delete | E2E test only verifies row visibility, not full delete lifecycle | Enhance to verify DB deletion + balance update |
| Date Range Filter | No E2E for transaction date range filtering | Add `test_filter_by_date_range` |
| Keyboard Navigation | No E2E for Tab order, Escape key, arrow keys in combobox | Add `test_keyboard_nav_focus_order`, `test_escape_closes_sheet` |
| Data Isolation | No E2E for cross-user access (only unit tests) | Add E2E test that authenticates as user_a, tries to access user_b's resource |
| Performance | No load testing for 1000+ transactions | Consider future performance tests (not P0) |

---

## Using This Document

1. **When writing new tests:** Find your feature section, follow the scenario pattern
2. **When planning manual QA:** Work through the preconditions → scenarios → expected results
3. **When debugging failures:** Find the gap label for that feature, understand what's missing
4. **When designing new features:** Follow the same pattern (preconditions, happy path, error paths, isolation)

For test code examples, see:
- `backend/*/tests/test_services.py` — service-level patterns
- `backend/*/tests/test_views.py` — view-level patterns
- `e2e/tests/test_*.py` — E2E test patterns
