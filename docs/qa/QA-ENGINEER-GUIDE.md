# ClearMoney — Manual QA Engineer Guide

> For human testers and AI agents running manual or exploratory QA sessions.  
> Last updated: 2026-04-17

---

## Quick Start (Get Running in 5 Minutes)

```bash
# 1. Start the DB (Docker)
docker-compose up -d db

# 2. Create a fresh QA test user
make qa-user EMAIL=qa@clearmoney.app PASSWORD=qatest123

# 3. Seed test data (institution, accounts, transactions, budgets)
make qa-seed

# 4. Start the app
make run

# 5. Get the magic link to log in (dev mode — no email sent)
make qa-login EMAIL=qa@clearmoney.app
# → prints http://localhost:8000/auth/verify?token=XXXX
# → paste into browser or Playwright MCP
```

---

## Environment Setup

### Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Docker running | any | `docker-compose ps` shows `db` Up |
| DB accessible | port 5433 | `make qa-user EMAIL=test@x.com` succeeds |
| Django server | port 8000 | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/` → 302 |

### Remote (Claude Code Web) vs Local

- **Local dev**: DB on port 5433 (Docker maps 5433→5432)
- **Remote / CI**: DB on port 5432 (native PostgreSQL). See `.claude/rules/remote-environment.md`
- The `DB_URL` Makefile variable defaults to port 5433; override with `DB_URL=postgres://...@localhost:5432/...`

### WeasyPrint (PDF Export)

PDF export requires native system libs. Without them, `/reports/export-pdf` returns 500.

```bash
# macOS (Homebrew)
brew install pango cairo

# Ubuntu/Debian
apt-get install -y libpango-1.0-0 libpangocairo-1.0-0
```

See ticket #119 for current workaround status.

---

## Make Commands Reference

```bash
make qa-user EMAIL=<email> PASSWORD=<password>   # Create superuser for QA
make qa-login EMAIL=<email>                       # Print magic link URL to console
make qa-seed                                      # Seed standard test data for QA user
make qa-teardown EMAIL=<email>                    # Delete QA user and all their data
make qa-reset EMAIL=<email>                       # teardown + qa-user + qa-seed (clean slate)
```

---

## Test Data Baseline (after `make qa-seed`)

After seeding, the QA user (`qa@clearmoney.app`) will have:

| Entity | Detail |
|--------|--------|
| Institution | "QA Test Bank" |
| Account: Main Checking EGP | Current, EGP, balance 10,000 |
| Account: Savings EGP | Savings, EGP, balance 0 |
| Account: USD Account | Current, USD, balance 500 |
| Account: Credit Card EGP | Credit Card, EGP, balance -2,000, limit 20,000 |
| Transactions | 4 transactions: salary (income 5,000), grocery (expense 500), transport (expense 200), restaurant (expense 1,000) |
| Budget: Food & Groceries | 3,000 EGP/month |
| Budget: Transport | 500 EGP/month |
| Tags | vacation, work-expense, family |

---

## Manual Test Execution Workflow

### For AI Agents (Playwright MCP)

```
1. make qa-reset EMAIL=qa@clearmoney.app PASSWORD=qatest123
2. make qa-login EMAIL=qa@clearmoney.app → grab token URL
3. mcp__playwright__browser_navigate(token URL) → lands on dashboard
4. Execute test scenarios below using browser_snapshot + browser_click + browser_evaluate
5. File bug tickets in .tickets/pending/ with screenshots in .tickets/attachments/
```

### For Human Testers

```
1. Open http://localhost:8000/login
2. Enter qa@clearmoney.app → click Continue
3. Run: make qa-login EMAIL=qa@clearmoney.app → open the printed URL
4. Execute scenarios; record results in ticket #117
```

---

## Test Scenarios Cheatsheet

### CP-2: Create Transaction + Verify Balance

```
1. Dashboard → click + (Add transaction)
2. Enter Amount: 500, Category: Food & Groceries, Note: "Test expense"
3. Click Save
4. Dashboard balance should decrease by 500
5. DB check: make qa-check-balance ACCOUNT_ID=<id> EXPECTED=<n>
```

### CP-3: Transfer Between Accounts

```
1. Dashboard → + → Move Money tab
2. From: Main Checking EGP, To: Savings EGP, Amount: 1000
3. Click Move Money
4. Verify: Checking -1000, Savings +1000, net worth unchanged
```

### CP-2 Edge: Same-Account Transfer

```
1. Move Money form → select same account for From and To
2. Submit → expect "Cannot transfer to the same account" error
```

### Test 013: Note Max Length

```
1. Quick Entry form → Note field
2. Type 501 characters → field should stop at 500 (maxlength=500)
3. Also verify future date is blocked (max=today on date input)
```

### Test RTL

```
1. Settings → click العربية button
2. Dashboard should flip to RTL, categories in Arabic
3. Verify no horizontal scroll on mobile viewport (375px)
4. Switch back with "English EN" button
```

### Test CSV Import

```
1. Settings → Upload CSV
2. Use: .tickets/attachments/test-import.csv (run make qa-seed-csv to generate)
3. Map columns → Preview → Submit
4. Verify transactions created and balance updated
```

---

## Finding and Filing Bugs

### Screenshot Naming Convention

```
.tickets/attachments/qa-NN-<feature>-<description>.png
```
Examples:
- `qa-01-dashboard-initial.png`
- `qa-05-same-account-transfer-error.png`

### Ticket Template for Bugs Found During QA

```markdown
---
id: "NNN"
title: "Bug: <one-line description>"
type: bug
priority: high|medium|low
status: pending
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

## Description
[What happened vs what was expected]

## Steps to Reproduce
1. ...

## Screenshot
See: `.tickets/attachments/qa-NN-<name>.png`

## Acceptance Criteria
- [ ] ...
```

### Severity Guide

| Priority | When to use |
|----------|------------|
| **high** | Financial data integrity (wrong balance, fee dropped, currency mixup) |
| **medium** | Feature broken (PDF 500, form validation missing, future dates allowed) |
| **low** | UI/UX issues (missing maxlength, untranslated strings, noisy banners) |

---

## Known Issues (as of 2026-04-17)

| Ticket | Issue | Priority |
|--------|-------|----------|
| #118 | Liquid Cash mixes currencies without conversion | high |
| #119 | PDF export returns 500 when WeasyPrint libs missing | medium |
| #120 | Move Money form allows future dates | medium |
| #121 | Fee amount silently dropped on transaction create | high |
| #122 | Multiple form inputs missing maxlength | low |
| #123 | RTL: section headings untranslated, "d left" fragments | medium |
| #124 | Reconciliation banners shown for brand-new accounts | low |

---

## Useful DB Queries for QA

```bash
# Check account balances
DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney" \
  uv run python -c "
import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clearmoney.settings'); django.setup()
from accounts.models import Account
from auth_app.models import User
u = User.objects.get(email='qa@clearmoney.app')
for a in Account.objects.filter(user_id=str(u.id)):
    print(f'{a.name}: {a.current_balance} {a.currency}')
" 2>/dev/null

# List recent transactions
DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney" \
  uv run python -c "
import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clearmoney.settings'); django.setup()
from transactions.models import Transaction
from auth_app.models import User
u = User.objects.get(email='qa@clearmoney.app')
for tx in Transaction.objects.filter(user_id=str(u.id)).order_by('-created_at')[:10]:
    print(f'{tx.type} {tx.amount} fee={tx.fee_amount} delta={tx.balance_delta} note={tx.note}')
" 2>/dev/null
```

---

## E2E Test Cross-Reference

When a manual test finds an issue, check the corresponding E2E test:

| Manual Test Area | E2E File |
|-----------------|----------|
| Login / magic link | `e2e/tests/test_auth.py` |
| Transaction CRUD + balance | `e2e/tests/test_transactions.py` |
| Transfers | `e2e/tests/test_transfers.py` |
| Dashboard panels | `e2e/tests/test_dashboard.py` |
| Budgets | `e2e/tests/test_budgets.py` |
| CSV Import | `e2e/tests/test_qa_csv_import.py` |
| Edge cases | `e2e/tests/test_qa_edge_cases.py` |

If the E2E test for a bug scenario **does not exist or does not cover the scenario**, note this in the bug ticket under a "Missing E2E Coverage" section.
