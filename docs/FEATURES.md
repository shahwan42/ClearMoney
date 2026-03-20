# ClearMoney — Feature Documentation

## Dashboard

The home page aggregates data from 10+ sources into a single view:

- **Net worth** — total across all accounts, with 30-day sparkline trend
- **Month-over-month spending** — current vs previous month with percentage change
- **Spending velocity** — daily spending rate projection for the month
- **Budget progress** — category bars (green/amber at 80%/red at 100%)
- **Virtual account balances** — envelope allocation overview
- **Credit card summary** — utilization, payment due dates, minimum payments
- **Account health warnings** — accounts below minimum balance or missing deposits
- **People summary** — outstanding loans/debts
- **Habit streak** — consecutive days with logged transactions
- **Recent transactions** — last 5 entries

## Accounts & Institutions

### Institutions
Banks and fintechs (HSBC, CIB, EGBank, Banque Misr, Telda, Fawry, TRU, etc.) serve as grouping containers for accounts. Each has a name, optional color, and display order.

- **Edit** — pencil icon on each card opens a bottom sheet with pre-filled Name and Type fields. On update, the card refreshes inline via HTMX OOB swap.
- **Delete with confirmation** — bottom sheet slides up requiring the user to type the institution name to confirm. Cascades to all accounts and their transactions (ON DELETE CASCADE).

### Account Types
- **Savings / Current / Prepaid** — standard accounts with EGP or USD balance
- **Credit Card** — tracks available credit (decrements on spend, restores on payment), billing cycle (statement date, due date), credit limit
- **Credit Limit** — revolving credit with EPP (Equal Payment Plan) support

### Account Features

- **Edit via bottom sheet** — lazy-loaded form with pre-filled values, updates account details inline
- **Delete with confirmation** — bottom sheet requires typing the account name to confirm. Cascades to transactions/snapshots, blocked by active installment plans
- Dormant toggle — keeps account in totals but de-prioritizes in UI
- Reordering — drag-to-reorder within institutions
- Health constraints — configurable min_balance and min_deposit rules (JSONB config)
- Balance sparklines — 30-day inline SVG trend per account
- Utilization donut — CSS conic-gradient chart for credit accounts

## Transactions

### Types
| Type | Behavior |
|------|----------|
| Expense | Debits the account, categorized |
| Income | Credits the account, categorized |
| Transfer | Paired debit/credit between own accounts |
| Exchange | Cross-currency transfer (USD→EGP) with exchange rate |

### Entry Methods
- **Standard form** — amount, account, category, date, note
- **Quick entry** — bottom sheet with smart category suggestion based on note text
- **Batch entry** — enter multiple transactions at once
- **Salary wizard** — multi-step distribution from income account to multiple destinations
- **Quick exchange** — exchange tab in the quick-entry bottom sheet for fast currency swaps

### Other Features
- Search and filter by date range, account, category, type
- Tag filtering
- Swipe-to-delete gesture (mobile)
- Each transaction stores a `balance_delta` field for reconciliation auditing
- Balance updates are atomic (transaction INSERT + balance UPDATE in a single DB transaction)
- Category dropdowns show emoji icons and group options by type (Expense / Income)

## Credit Cards

- **Statement view** — transactions grouped by billing period
- **Interest-free period tracking** — days remaining in grace period based on statement/due dates
- **Utilization donut** — visual spend vs limit
- **Utilization trends** — historical utilization over time
- **Payment guidance** — minimum payment, full balance, and statement balance options
- **Fawry cash-out** — credit card to cash conversion with fee tracking

## Reports

- **Monthly spending by category** — donut chart breakdown with drill-down
- **6-month income vs expenses** — bar chart comparison
- **Filters** — by account, category, date range
- **Backend**: `backend/reports/` — raw SQL aggregation + chart data computation

## Budgets

Monthly spending limits per category. Dashboard shows progress bars with three states:
- **Green** — under 80% of limit
- **Amber** — 80-100% of limit
- **Red** — over limit

CRUD via `/budgets` page. Budget data stored with category association and monthly limit.

## Virtual Accounts

Envelope-style budgeting system. Allows partitioning money across named goals/purposes:

- Create virtual accounts linked to a bank account, with optional target amounts
- **Direct allocations** — earmark existing funds from the VA detail page (no transaction created, bank balance unchanged)
- **Transaction-linked allocations** — select a VA when creating a transaction to allocate it automatically
- VA dropdown in transaction forms filters by the selected account (client-side JS)
- Server-side validation ensures VA's linked account matches the transaction's account
- Track progress toward each virtual account's goal
- Archive completed virtual accounts

## People (Loans & Debts)

Track informal lending and borrowing:

- Record loans to others and borrowings from others
- Log repayments
- Person detail page shows transaction history and payoff projection
- Dashboard shows net outstanding per person

## Recurring Rules

Automate repetitive transactions:

- **Auto-confirm** — transaction created automatically on schedule
- **Manual-confirm** — notification/prompt to confirm or skip
- Processed on app startup for any due rules

## Investments

Portfolio tracking for fund/stock holdings:
- Record holdings with units and price per unit
- Update valuations periodically
- Total portfolio value = sum(units * current_price)

## Installments

Payment plan tracking:
- Define total amount, number of installments, start date
- Track payments made vs remaining
- Progress indicator

## Exchange Rates

Historical USD/EGP exchange rate log. Used for:
- Currency exchange transactions
- Multi-currency net worth calculations

## Settings

- Dark mode toggle (class-based)
- CSV export of transactions
- Push notification subscription (VAPID-based)
- **Backend**: `backend/settings_app/` — settings page + CSV export endpoint

## Auth

Multi-user magic link authentication via Resend email API:
- **Login** → enter email → receive magic link → click → logged in (30-day session)
- **Registration** → enter email → magic link → click → account created + 25 default categories seeded
- Server-side database sessions (not HMAC tokens)
- All data isolated per user (`WHERE user_id = $N` on every query)
- Aggressive email quota protection: token reuse, per-email/IP/global daily caps, honeypot + timing checks
- Email enumeration prevention: unknown emails show same "Check your email" page, no email sent

## PWA

- `manifest.json` with app name, icons (192px, 512px), standalone display mode
- Service worker for offline caching
- Push notifications via Web Push API (VAPID keys)
- Pull-to-refresh gesture

## Charts (CSS-Only)

No JavaScript charting libraries. All charts use CSS and inline SVG:

| Chart | Implementation |
|-------|---------------|
| Donut | `conic-gradient()` with percentage segments |
| Bar | CSS flexbox with proportional heights |
| Sparkline | Inline SVG `<polyline>` with normalized coordinates |
| Trend | Arrow icon + percentage change text |

All charts support dark mode via Tailwind's `dark:` variants.

## Bottom Sheet Component

Reusable slide-up sheet with swipe-to-dismiss. Shared across accounts (4 sheets), account detail (2 sheets), and quick entry (1 sheet). Defined in `backend/templates/components/bottom_sheet.html` + `static/js/bottom-sheet.js`, with optional z-index and max-height params.

## UX Polish

- **Success animations** — toast notifications on form submissions
- **Skeleton loading** — placeholder cards/lists during HTMX requests
- **Smart category suggestions** — API endpoint suggests category based on transaction note
- **Swipe gestures** — swipe-to-delete on transaction rows
- **Empty states** — helpful messaging when lists are empty
- **Dark mode** — full dark mode with class-based toggling
- **Clickable header** — ClearMoney logo/title navigates to dashboard
- **Date pre-population** — all date inputs default to today via server-side rendering

## Rate Limiting

Per-user rate limiting via `django-ratelimit`:

- **Login routes** — 5 req/min (prevents brute-force attempts)
- **API routes** — 60 req/min (moderate protection for JSON endpoints)
- **Page routes** — 120 req/min (generous for normal browsing + HTMX)
- Static files and health check are exempt
- Returns 429 with `Retry-After` header; HTMX requests get styled HTML error partial

## Logging

Structured 3-layer logging for debugging and usage analytics:

- **Request middleware** (`StructuredLogger`) — status, duration, bytes, route pattern, HTMX detection, device type
- **Service events** (`logutil.LogEvent`) — 37 structured events across all mutating operations (entity.action format)
- **Page views** — 22 full pages + 10 HTMX partials logged at Info level
- **Debug tracing** — dashboard source timing, complex method entry, template rendering (enabled with `LOG_LEVEL=debug`)
- Skips `/static/*` and `/healthz` to reduce noise
- Request correlation via `request_id` across all log layers
