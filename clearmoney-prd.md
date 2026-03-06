# ClearMoney — Product Requirements Document

**Version:** 1.0
**Author:** Ahmed
**Date:** March 2026
**Status:** Draft

---

## 1. Executive Summary

ClearMoney is a mobile-first Progressive Web App (PWA) for personal finance management. It is purpose-built for a complex, multi-bank, multi-currency financial life common in Egypt's banking landscape — where a single person may hold accounts across HSBC, CIB, EGBank, Banque Misr, and fintechs like Telda, Fawry, and TRU, each with different account types, currencies, and quirks.

The core problem: there is no single pane of glass to see your full financial position when your money is fragmented across 15+ accounts, two currencies, credit lines, installment plans, investments, debts, and a building fund you manage on behalf of your neighbors.

ClearMoney solves this through manual-first transaction entry (with an obsessively smooth UX), a clear at-a-glance financial dashboard, and smart handling of the patterns unique to this financial environment — currency exchange, InstaPay transfers, credit card cash-outs, and monthly salary distribution flows.

---

## 2. Problem Statement

### 2.1 Core Pain Points

1. **Fragmentation:** Money is spread across 15+ accounts in 5 banks/fintechs, in USD and EGP. No single tool provides a unified view.
2. **Manual tracking is tedious:** Most Egyptian banks lack open banking APIs. Tracking must be manual, so the UX for entering transactions must be exceptionally fast and frictionless.
3. **Complex money flows:** Salary arrives in USD, gets exchanged to EGP at a variable rate, then gets distributed to multiple channels (household, bills, savings, insurance, building fund). Tracking this cascade is error-prone.
4. **Credit card complexity:** Credit limits that count down from zero, 55-day billing cycles starting on the 4th, due dates on the 8th, and cash-out patterns via Fawry with fees.
5. **Mixed roles:** Some accounts serve dual purposes (e.g., the HSBC EGP checking account handles both personal expenses and building fund management).
6. **Debt and lending:** Outstanding USD debt, plus informal person-to-person lending/borrowing with no structured tracking.
7. **Investments:** Variable-return fund investments via Thndr that need periodic valuation updates.

### 2.2 Who Is This For?

**Primary user:** Ahmed — a senior software engineer in Egypt managing a complex multi-bank, multi-currency personal financial life. The app is built for personal use first, with architecture that could generalize later.

**Secondary consideration:** Arwa (spouse) may view the dashboard or enter household expenses in the future.

---

## 3. Product Vision & Principles

### 3.1 Vision

> Open ClearMoney, see exactly where you stand financially in under 3 seconds. Enter any transaction in under 10 seconds. Never lose track of money again.

### 3.2 Design Principles

1. **Manual-first, no excuses.** Since there are no bank APIs to rely on, the entire UX is optimized around fast, accurate manual entry. Every tap and keystroke matters.
2. **At-a-glance clarity.** The dashboard must answer "how much do I have, how much do I owe, and where is everything?" without scrolling.
3. **Reflect reality, don't idealize it.** The system models how money actually moves — including messy patterns like credit card cash-outs, variable exchange rates, building fund commingling, and informal lending.
4. **Progressive complexity.** Simple things (entering a coffee purchase) must be dead simple. Complex things (salary distribution, credit card reconciliation) are supported but never forced.
5. **Offline-capable.** As a PWA, the app must work offline for transaction entry and sync when connectivity returns.

---

## 4. User Stories & Requirements

### 4.1 Accounts & Setup

| ID | Story | Priority |
|----|-------|----------|
| A-1 | As a user, I can add a financial institution (bank or fintech) with a name and optional logo/color | P0 |
| A-2 | As a user, I can add accounts under an institution with: name, type (checking, savings, current, prepaid, credit card, credit limit), currency (EGP/USD), and optional metadata | P0 |
| A-3 | As a user, I can set an initial balance for each account | P0 |
| A-4 | As a user, I can mark an account as "dormant" so it appears in totals but is de-prioritized in the UI | P1 |
| A-5 | As a user, I can assign an account a "role" tag (e.g., primary-income, household, building-fund, insurance-deduction, salary-legacy) for smart filtering | P1 |
| A-6 | As a user, I can define a credit card's billing cycle (statement date, due date, credit limit) | P0 |
| A-7 | As a user, I can define a credit limit account (e.g., TRU) with its limit and repayment terms (EPP) | P0 |
| A-8 | As a user, I can reorder accounts and institutions to match my mental model | P2 |

### 4.2 Transactions — Core Entry

| ID | Story | Priority |
|----|-------|----------|
| T-1 | As a user, I can enter an expense transaction with: amount, account, category, date (defaults to now), and optional note — in under 10 seconds | P0 |
| T-2 | As a user, I can enter an income transaction (salary, transfer received, refund, etc.) | P0 |
| T-3 | As a user, I can enter a transfer between my own accounts, which creates a paired debit/credit entry | P0 |
| T-4 | As a user, I can enter a currency exchange transaction specifying: source account (USD), destination account (EGP), USD amount, exchange rate, resulting EGP amount — with the ability to enter any two of the three and auto-calculate the third | P0 |
| T-5 | As a user, I can enter a credit card transaction that correctly decrements the available credit | P0 |
| T-6 | As a user, I can enter a credit card payment that restores available credit | P0 |
| T-7 | As a user, entering a transaction shows me the new account balance immediately as confirmation | P1 |
| T-8 | As a user, I see smart defaults: the last-used account, today's date, and recently-used categories appear first | P1 |
| T-9 | As a user, I can duplicate a recent transaction and modify it (for recurring-ish expenses) | P1 |
| T-10 | As a user, I can batch-enter transactions if I've been offline or forgot to log for a few days | P2 |

### 4.3 Transactions — Special Patterns

| ID | Story | Priority |
|----|-------|----------|
| S-1 | As a user, I can record a Fawry credit-card-to-prepaid cash-out: charge amount, fee amount, source (credit card), destination (Fawry prepaid), and optional subsequent cash withdrawal | P1 |
| S-2 | As a user, I can record an InstaPay transfer with auto-calculated fee (0.1%, min 0.5, max 20 EGP) | P1 |
| S-3 | As a user, I can record a salary arrival and initiate a "distribution flow" — a guided multi-step entry: exchange rate → household allocation → bills → savings → building fund → discretionary | P1 |
| S-4 | As a user, I can record a person-to-person loan (I lent X to Y, or I borrowed X from Y) with optional expected return date | P1 |
| S-5 | As a user, I can record a loan repayment (partial or full) that updates the outstanding balance | P1 |
| S-6 | As a user, I can record an EPP (Equal Payment Plan) purchase from TRU with: total amount, number of installments, monthly amount, and start date | P2 |
| S-7 | As a user, I can record a building fund collection (income into the shared sub-ledger) or a building fund expense (outflow from the shared sub-ledger) | P1 |

### 4.4 Categories & Tags

| ID | Story | Priority |
|----|-------|----------|
| C-1 | As a user, I have a default set of expense categories: Household, Food & Groceries, Transport, Health, Education, Utilities (Mobile, Electricity, Gas, Internet), Gifts, Entertainment, Shopping, Subscriptions, Building Fund, Insurance, Fees & Charges, Debt Payment, Other | P0 |
| C-2 | As a user, I have a default set of income categories: Salary, Freelance, Investment Returns, Refund, Building Fund Collection, Loan Repayment Received, Other | P0 |
| C-3 | As a user, I can create, edit, and archive custom categories | P1 |
| C-4 | As a user, I can add freeform tags to any transaction for additional filtering (e.g., "vacation", "ramadan", "emergency") | P2 |

### 4.5 Dashboard & At-a-Glance View

| ID | Story | Priority |
|----|-------|----------|
| D-1 | As a user, the home screen shows my **net worth** = total assets − total liabilities, in my primary currency (EGP) with USD equivalent | P0 |
| D-2 | As a user, I see a **summary bar**: total liquid cash (EGP + USD converted), total credit used, total credit available, total debt | P0 |
| D-3 | As a user, I see a **per-institution breakdown** with expandable account balances | P0 |
| D-4 | As a user, I see a **this month's spending** total vs. last month, broken down by top categories | P1 |
| D-5 | As a user, I see a **recent transactions** feed (last 10–15) with quick-entry FAB (floating action button) always visible | P0 |
| D-6 | As a user, I see a **people ledger summary**: net amounts owed to/from people | P1 |
| D-7 | As a user, I see a **building fund balance** as a clearly separated sub-section (since it's other people's money I'm managing) | P1 |
| D-8 | As a user, I can set a preferred exchange rate (or use the last recorded rate) for dashboard currency conversion | P1 |
| D-9 | As a user, I see my **investment portfolio value** (last manually updated valuation from Thndr) | P2 |

### 4.6 Reports & Insights

| ID | Story | Priority |
|----|-------|----------|
| R-1 | As a user, I can view a monthly spending breakdown by category (bar or pie chart) | P1 |
| R-2 | As a user, I can view income vs. expenses over time (monthly trend line) | P1 |
| R-3 | As a user, I can view account balance history over time | P2 |
| R-4 | As a user, I can view credit card utilization over time and upcoming due amounts | P2 |
| R-5 | As a user, I can filter any report by: date range, account, category, tag, currency | P2 |
| R-6 | As a user, I can view my exchange rate history (rate per salary cycle) | P2 |
| R-7 | As a user, I can export transactions as CSV for a given date range | P2 |

### 4.7 Recurring & Scheduled

| ID | Story | Priority |
|----|-------|----------|
| RC-1 | As a user, I can define recurring transactions (e.g., monthly savings deposit to CIB, monthly insurance deduction, mobile bill) with amount, account, category, and frequency | P2 |
| RC-2 | As a user, the app reminds me of upcoming recurring transactions and lets me confirm/adjust/skip them | P2 |
| RC-3 | As a user, I see upcoming credit card due dates and estimated amounts due on the dashboard | P2 |

### 4.8 PWA & Offline

| ID | Story | Priority |
|----|-------|----------|
| P-1 | As a user, I can install the app on my phone's home screen | P0 |
| P-2 | As a user, I can enter transactions offline and they sync when I'm back online | P1 |
| P-3 | As a user, the app loads fast (<2s) and feels native on mobile | P0 |
| P-4 | As a user, I get push notifications for reminders (credit card due dates, recurring transactions) | P2 |

---

## 5. Data Model

### 5.1 Core Entities

```
Institution
├── id (UUID)
├── name (e.g., "HSBC", "Telda")
├── type (bank | fintech)
├── color (hex, for UI)
├── icon (optional, stored path)
├── display_order (integer)
├── created_at, updated_at

Account
├── id (UUID)
├── institution_id (FK → Institution)
├── name (e.g., "Checking Account")
├── type (checking | savings | current | prepaid | credit_card | credit_limit)
├── currency (EGP | USD)
├── current_balance (decimal, computed or cached)
├── initial_balance (decimal, set at creation)
├── credit_limit (decimal, nullable — for credit cards/TRU)
├── is_dormant (boolean)
├── role_tags (text[], e.g., ["primary-income", "building-fund"])
├── display_order (integer)
├── metadata (JSONB — billing cycle info, minimum balance, etc.)
├── created_at, updated_at

Transaction
├── id (UUID)
├── type (expense | income | transfer | exchange | loan_out | loan_in | loan_repayment)
├── amount (decimal, always positive)
├── currency (EGP | USD)
├── account_id (FK → Account, the primary account affected)
├── counter_account_id (FK → Account, nullable — for transfers/exchanges)
├── category_id (FK → Category)
├── date (date)
├── time (time, optional)
├── note (text, optional)
├── tags (text[])
├── exchange_rate (decimal, nullable — for exchange transactions)
├── counter_amount (decimal, nullable — the amount in the other currency)
├── fee_amount (decimal, nullable — InstaPay fee, ATM fee, etc.)
├── fee_account_id (FK → Account, nullable — if fee is charged to a different account)
├── person_id (FK → Person, nullable — for P2P lending)
├── linked_transaction_id (FK → Transaction, nullable — pairs transfers/exchanges)
├── is_building_fund (boolean, default false)
├── recurring_rule_id (FK → RecurringRule, nullable)
├── created_at, updated_at

Category
├── id (UUID)
├── name
├── type (expense | income)
├── icon (optional)
├── is_system (boolean — true for defaults, false for user-created)
├── is_archived (boolean)
├── display_order (integer)

Person
├── id (UUID)
├── name
├── note (optional)
├── net_balance (decimal, computed — positive = they owe me, negative = I owe them)
├── created_at, updated_at

RecurringRule
├── id (UUID)
├── template_transaction (JSONB — all fields of a transaction except date)
├── frequency (monthly | weekly | custom)
├── day_of_month (integer, nullable)
├── next_due_date (date)
├── is_active (boolean)
├── auto_confirm (boolean — if true, create automatically; if false, prompt for confirmation)
├── created_at, updated_at

Investment
├── id (UUID)
├── platform (e.g., "Thndr")
├── fund_name (e.g., "AZG", "AZO", "BCO", "BMM")
├── units (decimal)
├── last_unit_price (decimal)
├── last_valuation (decimal, computed)
├── last_updated (timestamp)
├── currency (EGP)
├── created_at, updated_at

ExchangeRateLog
├── id (UUID)
├── date (date)
├── rate (decimal — EGP per 1 USD)
├── source (e.g., "HSBC/CBE", "market", "manual")
├── note (optional, e.g., "salary exchange March 2026")
├── created_at

InstallmentPlan
├── id (UUID)
├── account_id (FK → Account, e.g., TRU credit limit)
├── description (text)
├── total_amount (decimal)
├── num_installments (integer)
├── monthly_amount (decimal)
├── start_date (date)
├── remaining_installments (integer)
├── created_at, updated_at
```

### 5.2 Key Relationships

- Each `Transaction` belongs to one `Account` and optionally links to a `counter_account` (for transfers/exchanges).
- Transfer and exchange transactions create **two linked rows** (one debit, one credit) connected via `linked_transaction_id`.
- The `Person` entity tracks net lending/borrowing balances.
- `Building fund` transactions are tagged with `is_building_fund = true` and always use the HSBC EGP Checking Account, allowing the building fund to be reported as a virtual sub-ledger.
- `RecurringRule` generates `Transaction` records on schedule via a background job.
- `InstallmentPlan` tracks EPP purchases and decrements `remaining_installments` as monthly payments are recorded.

### 5.3 Balance Computation Strategy

Account balances are maintained using a **cached balance + event log** approach:

1. `Account.current_balance` is a cached value updated on every transaction insert/update/delete.
2. The true balance can always be recomputed: `initial_balance + SUM(credits) - SUM(debits)`.
3. A nightly PostgreSQL job reconciles cached balances against computed balances and flags discrepancies.
4. Credit card balances are stored as negative values (0 = no usage, -500000 = fully utilized for the HSBC card).

---

## 6. Architecture & Tech Stack

### 6.1 Stack Overview

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend** | Go (stdlib + chi router) | Fast, single binary, excellent for a solo developer. Chi for routing ergonomics without framework overhead. |
| **Frontend** | HTMX + Go templates | Server-rendered HTML with HTMX for SPA-like interactions. Minimal JS. Perfect for a manual-entry-heavy app where forms and partial page updates dominate. |
| **Styling** | Tailwind CSS (via CDN or build) | Utility-first CSS for rapid mobile-first UI development. |
| **Database** | PostgreSQL 16 | Primary data store, plus `pg_cron` for scheduled jobs, `LISTEN/NOTIFY` for pub/sub, and `SKIP LOCKED` advisory locks for job queues. |
| **Job Queue** | PostgreSQL-backed (pgq pattern) | A `jobs` table with status, payload, retry logic. Workers poll with `SELECT ... FOR UPDATE SKIP LOCKED`. Avoids adding Redis/RabbitMQ. |
| **Caching** | PostgreSQL materialized views + application-level caching | Dashboard aggregations as materialized views refreshed on transaction changes. |
| **Deployment** | Docker Compose on Ubuntu VPS | Single `docker-compose.yml` with Go app + PostgreSQL. Identical local and production environments. Caddy or Traefik as reverse proxy for HTTPS. |
| **PWA** | Service Worker + Web App Manifest | Offline transaction queue, home screen install, push notifications via Web Push API. |

### 6.2 Project Structure

```
clearmoney/
├── cmd/
│   └── server/
│       └── main.go                 # Entry point
├── internal/
│   ├── config/                     # Environment & configuration
│   ├── database/                   # PostgreSQL connection, migrations
│   │   └── migrations/             # SQL migration files
│   ├── models/                     # Domain structs (Account, Transaction, etc.)
│   ├── repository/                 # Data access layer (queries)
│   ├── service/                    # Business logic layer
│   ├── handler/                    # HTTP handlers (one file per domain)
│   ├── middleware/                 # Auth, logging, rate limiting
│   ├── jobs/                       # Background job definitions
│   └── templates/                  # Go HTML templates
│       ├── layouts/                # Base layout, nav, etc.
│       ├── pages/                  # Full page templates
│       ├── partials/               # HTMX partial fragments
│       └── components/             # Reusable UI components
├── static/
│   ├── css/                        # Tailwind output
│   ├── js/                         # Minimal JS (service worker, HTMX config)
│   ├── icons/                      # PWA icons
│   ├── manifest.json               # PWA manifest
│   └── sw.js                       # Service worker
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── .env.example
└── README.md
```

### 6.3 Key Architectural Decisions

**Why HTMX over a SPA framework?**
The app is form-heavy and read-heavy. HTMX gives SPA-like partial page updates (swap a transaction list after entry, update a balance chip without full reload) while keeping all logic server-side in Go. No build step for JS. No API versioning. No state management library. The server renders HTML fragments and HTMX swaps them in. This is ideal for a solo developer who wants speed and simplicity.

**Why PostgreSQL for everything?**
Fewer moving parts. PostgreSQL handles: relational data (accounts, transactions), JSONB for flexible metadata, `pg_cron` or application-level cron for recurring jobs, `LISTEN/NOTIFY` for real-time dashboard refresh, and a simple job queue via `SKIP LOCKED`. This avoids introducing Redis, RabbitMQ, or any other infrastructure dependency.

**Why Docker Compose?**
Exact same environment locally and on the VPS. The compose file defines two services: the Go app and PostgreSQL. Caddy runs on the host (or as a third service) for automatic HTTPS. Deploying is `git pull && docker compose up -d --build`.

### 6.4 Offline Architecture

```
[Browser]
  ├── Service Worker (sw.js)
  │   ├── Cache: app shell (HTML, CSS, JS, icons)
  │   ├── Cache: last-fetched dashboard data
  │   └── IndexedDB: offline transaction queue
  │
  └── On transaction entry while offline:
      1. Save to IndexedDB queue
      2. Show optimistic UI update
      3. When online → POST queued transactions to server
      4. Server responds with updated balances
      5. Clear queue, refresh dashboard
```

---

## 7. API & HTMX Endpoints

Since HTMX works by returning HTML fragments, the "API" is a set of endpoints that return either full pages or HTML partials.

### 7.1 Page Endpoints (Full HTML)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard (home) |
| GET | `/accounts` | Account list & management |
| GET | `/accounts/{id}` | Single account detail + transaction history |
| GET | `/transactions` | Full transaction list with filters |
| GET | `/transactions/new` | New transaction form |
| GET | `/people` | People ledger (loans/borrowing) |
| GET | `/reports` | Reports & charts |
| GET | `/settings` | App settings, categories, export |

### 7.2 HTMX Partial Endpoints

| Method | Path | Returns | Trigger |
|--------|------|---------|---------|
| POST | `/transactions` | Updated transaction list + balance chip | Transaction form submit |
| GET | `/partials/balance-summary` | Dashboard summary bar | After any transaction change |
| GET | `/partials/recent-transactions` | Recent transactions feed | Dashboard refresh |
| GET | `/partials/account-balance/{id}` | Single account balance chip | After transaction on that account |
| POST | `/transactions/quick` | Confirmation toast + updated feed | Quick-entry form |
| GET | `/partials/category-suggest?q=` | Category autocomplete dropdown | Typing in category field |
| POST | `/accounts` | Updated institution list | New account form |
| PUT | `/transactions/{id}` | Updated transaction row | Edit transaction |
| DELETE | `/transactions/{id}` | Removal animation + updated balance | Delete transaction |
| POST | `/exchange` | Exchange confirmation + updated balances | Currency exchange form |
| POST | `/salary-distribution` | Step-by-step wizard partials | Salary distribution flow |
| GET | `/partials/people-summary` | People ledger summary | Dashboard section |
| GET | `/partials/building-fund` | Building fund balance card | Dashboard section |

### 7.3 Offline Sync Endpoint

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sync/transactions` | Accepts a batch of offline-queued transactions, processes them, returns updated balances |

---

## 8. UI/UX Specification

### 8.1 Mobile-First Layout

The app is designed for a ~375px viewport first, scaling up gracefully.

```
┌─────────────────────────────┐
│  ClearMoney        [≡] [⚙] │  ← Sticky header
├─────────────────────────────┤
│                             │
│  NET WORTH                  │
│  ████████  EGP 1,234,567    │
│  ████████  $12,345 USD      │
│                             │
│  ┌──────┐ ┌──────┐ ┌──────┐│
│  │ Cash │ │Credit│ │ Debt ││
│  │ 890K │ │-120K │ │-21K$ ││
│  └──────┘ └──────┘ └──────┘│
│                             │
│  ─── Accounts ───────────── │
│  ▼ HSBC                     │
│    Checking USD    $4,500   │
│    Checking EGP    LE 45K   │
│    Credit Card    -LE 120K  │
│  ▶ CIB                     │
│  ▶ Banque Misr              │
│  ...                        │
│                             │
│  ─── Recent ─────────────── │
│  ● Groceries     -LE 1,200 │
│  ● Salary        +$3,500   │
│  ● InstaPay fee  -LE 20    │
│  ...                        │
│                             │
├─────────────────────────────┤
│  [🏠] [📊] [👥]     [＋]  │  ← Bottom nav + FAB
└─────────────────────────────┘
```

### 8.2 Transaction Entry UX (The Critical Flow)

The "add transaction" experience is the make-or-break UX of the entire app. It must be fast, forgiving, and encouraging.

**Quick Entry (FAB → Bottom Sheet)**

1. Tap the `[＋]` FAB → bottom sheet slides up
2. **Amount** field is auto-focused with a large numeric keypad
3. Type amount → tap next
4. **Account** selector: shows recent/favorite accounts first, with institution color coding. Tapping selects.
5. **Category** selector: icon grid of most-used categories, with a search bar. Tapping selects.
6. **Date** defaults to today, tappable to change
7. **Note** optional, one-line text input
8. **Save** button — large, satisfying, with haptic feedback (vibration API)
9. On save: brief success animation (checkmark + the new balance), sheet dismisses, feed updates via HTMX

**Design goals for this flow:**
- 3 taps minimum path: amount → account → category → save
- Never more than 2 seconds between taps waiting for UI
- The sheet remembers your last-used account and pre-selects it
- Category icons use color and shape, not just text, for fast recognition
- If the same category is used 3+ times in a row, it becomes the default

**Transfer Entry:**
- Select "Transfer" type → shows source account, destination account, amount
- If accounts are different currencies → automatically shows exchange rate field
- InstaPay fee auto-calculated and shown as a sub-line

**Salary Distribution Wizard:**
- Triggered manually or suggested when a large USD income is logged to the HSBC USD account
- Step 1: Confirm salary amount (USD)
- Step 2: Enter exchange rate → auto-calculates EGP equivalent
- Step 3: Allocation screen — pre-filled with last month's distribution, editable
  - Household: LE ___
  - Bills (expandable): Mobile, Electricity, Gas, Internet
  - Savings (expandable): CIB Primary, CIB Insurance, BM Insurance
  - Building Fund: LE ___
  - Discretionary: LE ___ (auto-calculated remainder)
- Step 4: Review → Confirm → Creates all transactions at once

### 8.3 Visual Design Direction

- **Color palette:** Dark mode primary (easier on eyes for financial data), with a clean light mode option. Accent color: a confident teal/green for positive balances, warm amber for warnings, red for negative/overdue.
- **Typography:** System font stack for performance. Large, bold numbers for amounts. Clear hierarchy.
- **Animations:** Subtle but meaningful — balance count-up on change, smooth sheet transitions, gentle category icon bounces on selection.
- **Encouraging UX:** After saving a transaction, show a micro-celebration: "Logged! You're 12 transactions in this week." or "Your tracking streak: 15 days." Small dopamine hits to reinforce the manual entry habit.

### 8.4 Navigation

Bottom navigation with 3 primary tabs plus the FAB:

1. **Home** (🏠) — Dashboard with net worth, summaries, recent transactions
2. **Reports** (📊) — Charts, breakdowns, trends
3. **People** (👥) — Lending/borrowing ledger
4. **[＋] FAB** — Always visible, always accessible. This is the most important button in the app.

Settings accessible from the header gear icon. Accounts management accessible from the dashboard's accounts section.

---

## 9. Security & Authentication

### 9.1 Authentication

- **Single-user mode (v1):** Simple PIN or password on the PWA. No email/OAuth complexity. The app is for personal use on a personal device.
- **Session:** HTTP-only secure cookie, 30-day expiry, re-authentication on sensitive actions (export, delete account).
- **Future (v2):** Optional second user (Arwa) with role-based access (view-only, or household-expense entry only).

### 9.2 Data Security

- HTTPS enforced via Caddy auto-TLS on the VPS.
- Database credentials in environment variables, never in code.
- No sensitive data in URLs or query parameters.
- Daily automated PostgreSQL backups to an external location (e.g., S3-compatible storage or a second VPS).
- PIN/password hashed with bcrypt.

---

## 10. Deployment & DevOps

### 10.1 Local Development

```bash
# Clone and start
git clone <repo>
cd clearmoney
cp .env.example .env
docker compose up -d

# App available at http://localhost:8080
# PostgreSQL at localhost:5432
# Hot reload via Air (Go live reload tool)
```

### 10.2 Production Deployment

```bash
# On VPS (Ubuntu 24.04)
# Caddy installed on host for reverse proxy + auto HTTPS

# Deploy
ssh vps "cd /opt/clearmoney && git pull && docker compose up -d --build"

# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "8080:8080"
    env_file: .env
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    env_file: .env
    restart: unless-stopped

volumes:
  pgdata:
```

### 10.3 Backup Strategy

- `pg_dump` daily via `pg_cron` or a cron job on the host
- Compressed and uploaded to external storage
- Retain 30 days of daily backups
- Test restore procedure monthly

---

## 11. Development Phases

### Phase 1 — Foundation (Weeks 1–3)
**Goal:** Core infrastructure, account management, basic transaction entry.

- Project scaffolding: Go project, Docker Compose, PostgreSQL, migrations
- User authentication (PIN-based)
- Institution & Account CRUD
- Transaction entry (expense, income) with basic form
- Dashboard: net worth, account balances list
- PWA manifest + service worker (app shell caching)
- Mobile-first responsive layout with Tailwind

**Deliverable:** Can add accounts, enter basic transactions, see balances on the dashboard.

### Phase 2 — Transaction Excellence (Weeks 4–6)
**Goal:** All transaction types, optimized entry UX, transfers, and exchanges.

- Transfer between accounts (with linked transactions)
- Currency exchange with rate input
- Credit card transaction handling (available credit tracking)
- Quick-entry bottom sheet with smart defaults
- Category management (defaults + custom)
- Recent transactions feed on dashboard
- Account detail page with transaction history
- InstaPay fee auto-calculation

**Deliverable:** Can handle the full range of daily financial operations with a smooth entry UX.

### Phase 3 — Advanced Features (Weeks 7–9)
**Goal:** Special patterns, people ledger, building fund, insights.

- Salary distribution wizard
- Fawry cash-out flow
- People ledger (lending/borrowing)
- Building fund sub-ledger
- Monthly spending breakdown (reports page)
- Income vs. expenses trend chart
- Credit card billing cycle tracking
- Dashboard summary cards (cash, credit, debt)
- Offline transaction queue (IndexedDB + sync)

**Deliverable:** Full feature set for daily use. App is genuinely useful for managing the complete financial picture.

### Phase 4 — Polish & Delight (Weeks 10–12)
**Goal:** Recurring transactions, investments, notifications, export, UX polish.

- Recurring transaction rules + reminders
- Investment portfolio tracking (manual valuation entry)
- Installment plan tracking (TRU EPP)
- Exchange rate history log
- Push notifications (credit card due dates, recurring reminders)
- CSV export
- Dormant account handling
- Transaction search and filtering
- Performance optimization (materialized views, query tuning)
- Tracking streak / habit encouragement UI
- Final UX polish, animations, edge cases

**Deliverable:** Production-ready app for daily personal use.

---

## 12. Success Metrics

| Metric | Target |
|--------|--------|
| Transaction entry time (amount → save) | < 10 seconds |
| Dashboard load time | < 2 seconds |
| Daily transaction logging consistency | > 90% of days in a month |
| Balance accuracy (cached vs. computed) | 100% match on nightly reconciliation |
| Offline transaction sync success rate | > 99% |
| Time to answer "what's my financial position?" | < 3 seconds (open app → see dashboard) |

---

## 13. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Manual entry fatigue — stops logging after initial excitement | High | Critical | Obsessive UX optimization, habit streaks, smart defaults, duplication, batch entry |
| Balance drift — manual entries diverge from real bank balances | Medium | High | Monthly reconciliation prompts, easy balance adjustment entries |
| Scope creep — trying to build too much before daily use | Medium | High | Phase 1 must be usable on its own. Ship early, iterate. |
| Data loss on VPS | Low | Critical | Automated daily backups, tested restore procedure |
| Exchange rate complexity — rounding errors compound | Medium | Medium | Store rates to 4+ decimal places, always store both amounts in exchange transactions |
| Building fund accounting confusion | Medium | Medium | Clear visual separation, `is_building_fund` flag, dedicated sub-section on dashboard |

---

## 14. Future Considerations (Post-MVP)

These are explicitly out of scope for the initial build but worth keeping in mind architecturally:

- **Multi-user support:** Arwa as a second user with household expense entry permissions.
- **Bank statement import:** CSV/PDF parsing for bulk reconciliation.
- **Open banking integration:** If Egyptian banks ever offer APIs, the architecture should support automated transaction import.
- **Budgeting:** Set monthly budgets per category with progress tracking.
- **Financial goals:** Savings goals with progress visualization.
- **Receipt capture:** Photo attachment on transactions via camera API.
- **Telegram/WhatsApp bot:** Quick transaction entry via messaging (send "coffee 85" to log an expense).
- **Multi-currency beyond USD/EGP:** EUR, GBP, SAR for travel or freelance.

---

## 15. Glossary

| Term | Definition |
|------|-----------|
| **EPP** | Equal Payment Plan — installment-based purchasing (e.g., TRU) |
| **InstaPay** | Egypt's instant payment network for inter-bank transfers, operated by EBC |
| **IPN** | Instant Payment Network — the infrastructure behind InstaPay |
| **CBE** | Central Bank of Egypt |
| **EBC** | Egyptian Banks Company, owned by CBE, operates InstaPay |
| **FAB** | Floating Action Button — the persistent "+" button for quick transaction entry |
| **Building Fund** | A shared financial pool managed by Ahmed on behalf of building residents |
| **Dormant Account** | An account with minimal activity, kept open but de-prioritized in the UI |
| **Linked Transaction** | A pair of transactions representing two sides of a transfer or exchange |
| **Net Worth** | Total assets (all positive balances + investments) minus total liabilities (credit used + debt) |
