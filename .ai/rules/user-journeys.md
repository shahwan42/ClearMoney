# User Journeys — ClearMoney Agent Map

> Distilled, step-by-step maps for an AI agent to perform common tasks without guesswork.
> Integrates with `[data-testid]` selectors from `agent-testing.md`.

## J-1: Setup & Environment Ready
*Goal: Get to a state where there is data to interact with.*

1. **Verify server alive (MANDATORY first step):**
   - `curl -fsS --max-time 5 http://0.0.0.0:8000/healthz` → expect `ok`.
   - `curl -s -o /dev/null -w '%{http_code}' http://0.0.0.0:8000/` → expect `302`.
   - Any other result → follow Server Liveness Protocol in `agent-testing.md`
     (kill `:8000` + restart) before continuing. Stale/hung servers cause every
     subsequent step to fail in misleading ways.
2. **Bypass Auth:** Navigate to `/login?dev=1`.
3. **Seed Data:** Navigate to `/dev/seed` (or click `[data-testid="dev-seed-button"]` in Settings).
4. **Verify Dashboard:** Ensure `main` contains "Net Worth".

## J-2: The Financial Loop (Create Expense)
*Goal: Record spending and verify balance impact.*

1. **Open Form:** Click `[data-testid="nav-plus"]`.
2. **Wait for Loading:** Wait for `body:not([data-htmx-loading])`.
3. **Fill Amount:** Type `500` into `#qe-amount`.
4. **Select Account:** Type name into `[data-testid="qe-account-combobox-input"]` and select.
5. **Select Category:** Type name into `[data-testid="qe-category-combobox-input"]` and select.
6. **Save:** Click `button[type="submit"]`.
7. **Verify:** Check that the success message appears and the dashboard balance decreased.

## J-3: Account Management
*Goal: Edit or update an existing account.*

1. **Navigate:** Click `[data-testid="nav-accounts"]`.
2. **Open Edit:** Find the account row and click its edit button (pencil icon).
3. **Modify:** Change the name or balance.
4. **Save:** Submit the form in the bottom sheet.
5. **Verify:** Ensure the row in the list updates immediately (HTMX partial swap).

## J-4: Budget Surveillance
*Goal: Check if spending is within limits.*

1. **Open Menu:** Click `[data-testid="nav-more"]`.
2. **Navigate to Budgets:** Click `[data-testid="menu-budgets"]`.
3. **Observe Progress:** Look for progress bars. 
    *   *Agent Tip:* Check for `bg-amber-500` (80% used) or `bg-red-500` (100%+ used) classes.

## J-5: Multi-User Isolation (Security Check)
*Goal: Verify User A cannot see User B's data.*

1. **User A:** Log in via `/login?dev=1` as `test@clearmoney.app`.
2. **Note IDs:** Capture an ID of a transaction or account.
3. **Switch User:** Clear cookies and log in as a different email.
4. **Attack:** Attempt to `GET` the captured ID (e.g., `/transactions/<id>`).
5. **Success Criteria:** HTTP 404 response (Forbidden/Not Found).

## Navigation Cheat Sheet

| Feature | Entry Point |
|---------|-------------|
| **People/Loans** | `More` → `[data-testid="menu-people"]` |
| **Investments** | `More` → `[data-testid="menu-investments"]` |
| **Recurring/Auto** | `More` → `[data-testid="menu-automations"]` |
| **Batch Entry** | `More` → `[data-testid="menu-batch"]` |
| **Reports** | `More` → `[data-testid="menu-reports"]` |
| **Settings** | `More` → `[data-testid="menu-settings"]` |
