# Critical Paths — ClearMoney

> These 6 user journeys MUST work at all times. A regression in any of these is a P1 bug.
> Use this checklist after major refactors, dependency upgrades, or when debugging a production incident.
> For each path: steps → verification → E2E file → regression definition.

---

## CP-1: Authentication — Magic Link Login

**Precondition:** Existing user in DB (test@clearmoney.app), user unauthenticated (no session cookie)

**Steps:**
1. GET `/` → redirect to `/login` (unauthenticated)
2. POST `/login` with valid email, timing > 2s
3. GET `/auth/verify?token=<valid_token>`
4. Verify session cookie `clearmoney_session` is set
5. Verify session row exists in `sessions` table
6. GET `/` → renders dashboard (authenticated)

**Verify at each step:**
- Step 1: `response.url` contains `/login`
- Step 2: Form accepts timing > 2s (anti-bot check passes)
- Step 3: HTTP 302 redirect to `/`
- Step 4: Cookie `clearmoney_session` present in browser
- Step 5: SQL query `SELECT * FROM sessions WHERE token = ...` returns one row
- Step 6: Dashboard renders, no 401 redirect

**E2E coverage:** [`e2e/tests/test_auth.py`](../../e2e/tests/test_auth.py) — `TestMagicLinkFlow::test_valid_token_creates_session_and_redirects`

**Regression definition:** Test fails OR `/` shows login page when session is valid

**Error paths that must also work:**
- Expired token (> 15 min) → "Link expired" message
- Used token (already verified) → "Link expired" message
- Honeypot filled (website field) → request rejected silently
- Timing < 2s → "too fast" anti-bot rejection

---

## CP-2: Core Financial Loop — Create Account → Add Transaction → Verify Balance

**Precondition:** Authenticated user, no accounts

**Steps:**
1. POST `/accounts/institutions` → create institution (Test Bank)
2. POST `/accounts` → create Current account (EGP, initial balance 10,000)
3. GET `/transactions/new` → transaction form loads
4. POST `/transactions` → create expense transaction (500 EGP, "Food" category)
5. Verify balance in UI = 9,500 EGP
6. Verify balance in DB = 9,500.00 (exact Decimal)

**Verify at each step:**
- Step 2: Account appears in `/accounts` list with balance 10,000
- Step 4: HTMX response status 200, contains "Transaction saved!" in `#transaction-result`
- Step 5: Dashboard or accounts page shows balance 9,500 (not 10,000)
- Step 6: SQL `SELECT current_balance FROM accounts WHERE id = ...` = 9500.00 (NUMERIC type, exact)

**E2E coverage:** [`e2e/tests/test_transactions.py`](../../e2e/tests/test_transactions.py) — `TestTransactionCRUD::test_create_expense_updates_balance`

**Regression definition:**
- Test fails OR
- Balance shown in UI ≠ DB balance OR
- Balance is float (e.g., 9500.0 instead of 9500.00) indicating precision loss

**Error paths:**
- Zero amount rejected (service ValueError → 400)
- Future date rejected (`max="{{ today }}"` on date input)
- Negative amount rejected
- Missing amount field → validation error shown

---

## CP-3: Transfer Flow — Verify Both Balances Update

**Precondition:** Authenticated user, two EGP accounts (EGP1: 20,000, EGP2: 0)

**Steps:**
1. GET `/transfers/new` → transfer form loads
2. Fill form: amount=5,000, source=EGP1, destination=EGP2
3. POST `/transactions/transfer` → HTMX submit
4. Verify HTMX response status 200, contains "Transfer completed!"
5. Navigate to `/accounts`
6. Verify EGP1 balance = 15,000 (20,000 - 5,000)
7. Verify EGP2 balance = 5,000 (0 + 5,000)
8. Navigate to `/` (dashboard) → net worth = 20,000 (unchanged)

**Verify at each step:**
- Step 4: `#transfer-result` contains success message
- Step 6: EGP1 balance shown as 15,000 in list
- Step 7: EGP2 balance shown as 5,000 in list
- Step 8: Net worth section still shows 20,000 (transfer is not a gain/loss, only redistribution)

**E2E coverage:** [`e2e/tests/test_transfers.py`](../../e2e/tests/test_transfers.py) — `TestTransfers::test_transfer_updates_both_balances`

**Regression definition:**
- Either balance is wrong OR
- Net worth changed (should remain same) OR
- Balance update not atomic (one account updated, other not)

**Error paths:**
- Same source + destination → 400 validation error
- Different currencies → rejected (use exchange instead)
- Missing rate for exchange → validation error

---

## CP-4: Budget Cycle — Create Budget → Spend → Verify Progress

**Precondition:** Authenticated user, account with EGP, one expense category (Food)

**Steps:**
1. POST `/budgets` → create budget (Food category, limit=2,000 EGP)
2. Navigate to `/budgets` → budget appears with 0/2,000 used
3. Create expense transaction: 500 EGP, Food category
4. Navigate back to `/budgets`
5. Verify budget shows 500/2,000 used (25% progress)
6. Verify text shows "1,500 remaining" (green indicator)
7. Navigate to `/` (dashboard)
8. Verify budget panel shows same 25% progress

**Verify at each step:**
- Step 2: Budget row: "0 used" + "2,000 limit" + "100% remaining"
- Step 5: Progress bar width ≈ 25% (CSS width calculation)
- Step 6: Text "1,500 remaining" visible
- Step 8: Dashboard budget panel data matches `/budgets` page

**E2E coverage:** [`e2e/tests/test_budgets.py`](../../e2e/tests/test_budgets.py) — `TestBudgets::test_budget_tracks_spending`

**Regression definition:**
- Budget percentage wrong OR
- Dashboard panel doesn't update after transaction OR
- Remaining amount calculation incorrect

**Error paths:**
- Duplicate budget (same category + currency) → 400
- Zero limit → 400 validation error
- Negative limit → 400

---

## CP-5: Dashboard — All Panels Render, No 500 Errors

**Precondition:** Authenticated user with: 1 institution, 1 account (10,000 EGP), 1 expense transaction

**Steps:**
1. GET `/` (dashboard home)
2. Verify HTTP 200 (not 500)
3. Verify net worth section visible ("Net Worth" heading)
4. Verify summary cards visible ("Liquid Cash", "Credit Used", "Credit Available")
5. Verify recent transactions list shows the transaction
6. Verify browser console has zero JavaScript errors
7. Check page for any broken images or 404 resources

**Verify at each step:**
- Step 2: Response status 200
- Step 3: Page contains text "Net Worth"
- Step 4: Page contains "Liquid Cash", "Credit Used" cards
- Step 5: Recent transactions section shows transaction note/amount
- Step 6: Open DevTools console → no error messages
- Step 7: Network tab shows no 404 responses

**E2E coverage:** [`e2e/tests/test_dashboard.py`](../../e2e/tests/test_dashboard.py) — all tests in class `TestDashboard`

**Regression definition:**
- Any test in test_dashboard.py fails OR
- HTTP 500 response OR
- Critical panel missing (net worth, summary, transactions)

**Error path (empty state):**
- User with no accounts → dashboard shows "Add your first account" CTA button
- CTA button links to `/accounts` (create account flow)

---

## CP-6: Session Security — Per-User Data Isolation

**Precondition:** Two users (user_a, user_b), each with one transaction

**Steps:**
1. Authenticate as user_a (obtain session cookie)
2. GET `/transactions` (list view)
3. Verify list contains only user_a's transaction (not user_b's)
4. GET `/transactions/<user_b_transaction_id>` (detail view)
5. Verify response status 404 (not user_a's data)
6. GET `/accounts/<user_b_account_id>`
7. Verify response status 404

**Verify at each step:**
- Step 2: Transaction list shows only 1 item (user_a's)
- Step 3: If user_b's transaction exists, it's NOT in the list
- Step 4: HTTP 404 response
- Step 5: Response body does not contain user_b's transaction data
- Step 6: HTTP 404 response
- Step 7: No information leakage (404 page is same as for nonexistent resource)

**Unit test coverage:** [`backend/transactions/tests/test_views.py`](../../backend/transactions/tests/test_views.py) — `TestTransactionDetail::test_404_for_other_users_tx`

**Regression definition:**
- Test fails OR
- HTTP 200 returned instead of 404 (data leak) OR
- user_a's list contains user_b's resources

**Note:** This critical path has **unit test coverage but NO E2E coverage**. E2E test for isolation is a known gap (see `docs/qa/TEST-FLOWS.md`).

---

## Running All Critical Paths

**Manual verification (comprehensive, ~10 min):**
1. `CP-1`: Follow login → verify → dashboard flow
2. `CP-2`: Create account → add expense → check balance
3. `CP-3`: Create two accounts → transfer → verify both
4. `CP-4`: Create budget → spend → check dashboard
5. `CP-5`: Navigate dashboard, check no errors
6. `CP-6`: Open two sessions in different browsers, verify isolation

**Automated verification (fast, ~3 min):**
```bash
make test-e2e          # Runs all E2E tests including CP-1 through CP-5
make test              # Unit tests including CP-6
```

**After production deploy or major refactor, run both.**

---

## Regression Recovery

If a critical path fails:

1. **Identify which CP is broken** (1-6 above)
2. **Check the E2E test file** listed in that CP section
3. **Run the specific test in verbose mode:**
   ```bash
   cd e2e && npx playwright test tests/test_auth.py -v  # for CP-1
   ```
4. **Inspect failure output** — browser snapshot, network requests, assertion error
5. **If test is flaky** (passes on retry): Check timing, database state, race conditions
6. **If test is broken** (fails consistently): Read the error, then check:
   - Did a recent commit change the view/service logic?
   - Did a migration break schema assumptions?
   - Are fixtures set up correctly in conftest.py?
7. **Debug path:**
   - Read the failing test code
   - Add `print()` or breakpoint to test
   - Inspect page snapshot with `page.screenshot()`
   - Check browser console for JS errors
   - Verify DB state with SQL query
8. **Once fixed, re-run that CP** before merging

---

## Agent Shortcuts (Dev Only)

To speed up manual verification and testing, use these internal tools (only active when `DEBUG=True`):

*   **Bypass Auth:** Navigate to `/login?dev=1` to instantly log in as `test@clearmoney.app`.
*   **Seed Data:** Navigate to `/dev/seed` to populate the DB with a full QA dataset (accounts, transactions, budgets).
*   **Observe HTMX:** Wait for `body:not([data-htmx-loading])` in Playwright scripts to ensure page stability.

See [Agent Testing Guide](./agent-testing.md) for full details.
