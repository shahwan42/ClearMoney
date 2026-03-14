# ClearMoney — Feature Documentation

## Dashboard

The home page aggregates data from 10+ sources into a single view:

- **Net worth** — total across all accounts, with 30-day sparkline trend
- **Month-over-month spending** — current vs previous month with percentage change
- **Spending velocity** — daily spending rate projection for the month
- **Budget progress** — category bars (green/amber at 80%/red at 100%)
- **Virtual fund balances** — envelope allocation overview
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

## Budgets

Monthly spending limits per category. Dashboard shows progress bars with three states:
- **Green** — under 80% of limit
- **Amber** — 80-100% of limit
- **Red** — over limit

CRUD via `/budgets` page. Budget data stored with category association and monthly limit.

## Virtual Funds

Envelope-style budgeting system (replaces the earlier building fund feature). Allows partitioning money across named goals/purposes:

- Create funds with target amounts
- Allocate transactions to specific funds
- Track progress toward each fund's goal
- Archive completed funds

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

- PIN change
- Dark mode toggle (class-based, persisted in user_config)
- CSV export of transactions
- Push notification subscription (VAPID-based)

## Auth

Single-user PIN-based authentication:
- First visit → setup flow to create 4-6 digit PIN
- PIN stored as bcrypt hash in `user_config` table
- Login generates HMAC session token in a 30-day cookie
- Auth middleware guards all routes except login/setup/health

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

## UX Polish

- **Success animations** — toast notifications on form submissions
- **Skeleton loading** — placeholder cards/lists during HTMX requests
- **Smart category suggestions** — API endpoint suggests category based on transaction note
- **Swipe gestures** — swipe-to-delete on transaction rows
- **Empty states** — helpful messaging when lists are empty
- **Dark mode** — full dark mode with class-based toggling
- **Clickable header** — ClearMoney logo/title navigates to dashboard
- **Date pre-population** — all date inputs default to today via server-side rendering
