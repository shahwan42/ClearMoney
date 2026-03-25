# ClearMoney React Native — Complete PRD Index

This directory contains comprehensive Product Requirements Documents (PRDs) for rebuilding ClearMoney as a native React Native application. These documents extracted from the production Django codebase provide the complete specification of features, edge cases, validation rules, API contracts, and data models.

## Quick Start

**Start here:** [01-DATA-MODELS.md](01-DATA-MODELS.md) → [02-API-SPECIFICATION.md](02-API-SPECIFICATION.md) → [03-AUTH-SECURITY.md](03-AUTH-SECURITY.md)

## Document Overview

### [01-DATA-MODELS.md](01-DATA-MODELS.md)
**18 models with complete specifications**
- User, Session, AuthToken, Institution, Account, Category, Person, RecurringRule
- Transaction, VirtualAccount, Budget, TotalBudget, Investment
- DailySnapshot, AccountSnapshot, ExchangeRateLog, UserConfig
- Every field documented: type, constraints, relationships, validation rules
- Data type mapping (DB → Python → JSON → React Native)
- 59 unique fields across all models
- Unique constraints and indexed columns
- Special handling: credit card signs, decimal arithmetic, ArrayField, JSONB

### [02-API-SPECIFICATION.md](02-API-SPECIFICATION.md)
**16 major API feature areas with complete endpoints**
- Authentication (magic link, session management, logout)
- Accounts & Institutions (CRUD, dormant status, health config)
- Transactions (create, update, delete, transfer, exchange, batch entry, sync)
- Budgets (monthly limits, category-specific, total budgets)
- Categories (CRUD, system defaults, archiving)
- People (loans, debt tracking, repayment)
- Virtual Accounts (envelope budgeting, allocations)
- Recurring Rules (scheduling, auto-confirm, pending rules)
- Reports (monthly breakdown, 6-month trends)
- Push Notifications (VAPID, polling-based check)
- Dashboard (net worth, sparklines, summaries)
- Settings & Export (CSV, user preferences)
- Investments (fund tracking, valuation updates)
- Common patterns: response format, error handling, rate limiting, timezone handling
- Mobile-specific notes: offline sync, session management, error recovery

### [03-AUTH-SECURITY.md](03-AUTH-SECURITY.md)
**Magic link auth, session management, permissions, data isolation**
- Complete magic link flow (login/registration unified endpoint)
- Token management (15-min TTL, single-use, reuse detection)
- Session management (30-day TTL, server-side validation)
- Rate limiting (3-tier: IP, per-email, authenticated user)
- Per-user data isolation (every query filtered by user_id)
- Ownership validation (delete/transfer verification)
- Middleware behavior (GoSessionAuthMiddleware)
- CSRF protection (honeypot + timing, no CSRF tokens)
- React Native implementation requirements
  - Bearer token vs cookies
  - Keychain/Keystore for secure token storage
  - Deep linking for email verification
  - Session timeout warnings
- API endpoints for mobile
- Multi-device session handling
- Error cases and responses
- Security checklist (16 items)
- Production checklist

### [04-BUSINESS-RULES.md](04-BUSINESS-RULES.md)
**Validation, edge cases, state consistency extracted from 40+ tests**
- Account creation (auto-naming, currency override, credit limits)
- Credit card rules (negative balance signs, utilization, billing cycles)
- Transaction validation (type, amount, currency, balance_delta)
- Transfer rules (same account check, cross-currency, fee handling, linked transactions)
- Exchange transactions (rate logging, counter amounts, precision)
- Uncategorized transactions (nullable category handling)
- People & loans (multi-currency, loan types, repayment impact)
- Budget rules (monthly scope, category-specific, duplicate prevention)
- Virtual account allocation (pivot table, non-transactional allocations)
- Recurring rules (frequency, template validation, processing)
- Exchange rate logging (global data, append-only)
- Data isolation & security (per-user filtering, service layer pattern)
- Numeric handling (Decimal arithmetic, precision, credit card math)
- Date & time handling (timezone awareness, billing cycles, streak counting)
- Cascading operations (delete impacts, cascading deletions)
- Background jobs (daily startup jobs, reconciliation, snapshots)
- Validation summary (21 fields with error messages)
- State consistency requirements (atomicity, denormalized fields, no orphans)
- What can fail & recovery strategies
- Numeric edge cases (very small amounts, division by zero, etc.)
- Data retention policy

### [05-UI-UX-FLOWS.md](05-UI-UX-FLOWS.md)
**Complete screen layouts, interactions, mobile patterns**
- Dashboard (net worth, sparklines, recent transactions, budgets, summary cards)
- Accounts (list, detail, create, edit, delete, dormant toggle, health config)
- Transactions (list, detail, create, update, delete, search, batch entry)
- Transfer flow (same-currency, cross-currency with exchange)
- Quick entry (minimal form, smart defaults)
- Batch entry (multiple transactions, partial failure handling)
- Categories (list, create, archive, optgroup structure)
- Budgets (create, list with progress, delete, total budget)
- People (list, create, loan/borrow, repayment, debt summary)
- Virtual accounts (create, allocate, progress tracking, warnings)
- Recurring rules (create, pending, confirm/skip, delete)
- Reports (monthly breakdown, 6-month trends, category filters)
- Settings (dark mode, CSV export, push notifications, user preferences)
- Auth screens (login/registration unified, check email, verification)
- Error states (network, validation, permission, timeout)
- Empty states (no transactions, no accounts, no budgets)
- Loading states (skeleton loading, spinners, progress bars)
- Mobile-specific UX (bottom sheet modals, pull-to-refresh, swipe gestures)
- Accessibility requirements (ARIA labels, focus management, keyboard navigation)

## Key Features Covered

### Complete Feature List
✅ **Dashboard** — net worth sparkline, month-over-month spending, budget progress, credit card summary
✅ **Accounts** — CRUD, institutions, dormant toggle, balance tracking, credit card utilization
✅ **Transactions** — CRUD, transfers, exchanges, quick entry, batch entry, search, filters
✅ **Categories** — system defaults (25+), custom categories, archiving
✅ **Budgets** — monthly limits per category, total budget, progress tracking
✅ **People** — loan tracking, debt repayment, multi-currency support
✅ **Virtual Accounts** — envelope budgeting, allocations, progress to goal
✅ **Recurring Rules** — scheduled transactions, auto-confirm, pending queue
✅ **Reports** — monthly breakdown, 6-month trends, category filters
✅ **Investments** — fund tracking, unit prices, valuations
✅ **Exchange Rates** — global reference data, rate history
✅ **Settings** — dark mode, CSV export, push notifications, user preferences
✅ **Auth** — magic link, sessions, multi-user, per-user isolation
✅ **Push Notifications** — VAPID keys, polling-based checking

### Edge Cases Documented
- Credit card balance signs (negative = debt)
- Transaction amount always positive (sign in balance_delta)
- Currency override from account (not form)
- Decimal precision (2 decimal places, 10.4 for rates)
- Multi-currency transactions (exchange rates, counter amounts)
- Transfer linking (debit/credit pairs)
- Virtual account over-allocation (warnings)
- Loan repayment direction (who owes whom)
- Recurring rule advancement (monthly vs weekly)
- Recurring template storage (JSONB serialization)
- Balance reconciliation (initial_balance + sum(deltas) = current)
- Running balance (window function, newest-first)
- Cascading deletes (account → transactions → allocations)
- User isolation (every query filtered by user_id)
- Session timeout (30 days, server-side validation)
- Rate limiting (3-tier: IP, email, authenticated)

### Validation Rules (55+ rules)
- Amount > 0 (always positive)
- Type must be valid enum
- Account must exist and belong to user
- Category optional but if provided must exist
- Transfer can't be same account
- Transfer requires same currency or exchange rate
- Credit card balance can't exceed limit
- Budget category unique per user+currency
- Virtual account name required
- Person name required
- Recurring frequency must be monthly or weekly
- Email required, normalized via lower()
- Token not used and not expired
- Fee amount ≥ 0
- And 40+ more...

## Data Coverage

**18 Models:**
- User, Session, AuthToken, Institution, Account, Category, Person, RecurringRule, Transaction, VirtualAccount, VirtualAccountAllocation, Budget, TotalBudget, Investment, DailySnapshot, AccountSnapshot, ExchangeRateLog, UserConfig

**16 Major API Areas:**
- Auth, Accounts & Institutions, Transactions, Budgets, Categories, People, Virtual Accounts, Recurring Rules, Reports, Push Notifications, Dashboard, Settings & Export, Investments, and more

**40+ Test Files Analyzed:**
- Extracted validation rules, edge cases, error handling
- Boundary conditions (amounts, dates, balances)
- Concurrent operations and atomicity
- State consistency and reconciliation
- Cascading operations and cleanup

## Architecture Patterns

### Per-User Data Isolation
Every table except ExchangeRateLog includes user_id. All queries must filter:
```python
accounts = Account.objects.for_user(user_id).filter(is_dormant=False)
```

### UserScopedManager Pattern
Custom Django manager ensures queries can't accidentally leak data:
```python
class UserScopedManager(BaseManager):
    def for_user(self, user_id: UUID) -> QuerySet:
        return self.filter(user_id=user_id)
```

### Magic Link Auth (No Passwords)
Single unified entry point (`POST /login`) auto-detects login vs registration.
- Anti-bot checks (honeypot + timing)
- Rate limiting (5-min cooldown, 3/day per email, 50/day global)
- Token reuse detection (no email re-send if unexpired)
- Single-use tokens (marked used immediately)
- 15-minute TTL on tokens
- 30-day TTL on sessions
- Server-side session validation on every request

### Atomic Balance Updates
Every transaction updates balance atomically:
```sql
UPDATE accounts SET current_balance = current_balance + balance_delta
WHERE id = account_id AND user_id = user_id
```

### Decimal Arithmetic (Not Floats)
All monetary values use `NUMERIC(15,2)` in DB, `Decimal` in Python, serialized as strings or floats in JSON.

### Append-Only Snapshots
Daily snapshots and account snapshots are append-only (never updated). Used for sparklines, net worth tracking, and audit trail.

## Mobile-Specific Requirements

### Session Management (No Cookies)
React Native can't use HTTP-only cookies. Instead:
- Store session token in Keychain/Keystore (secure OS storage)
- Include token in `Authorization: Bearer` header on every request
- Call `/api/session-status` every 5 minutes to check expiry
- Deep link support for email verification (clearmoney://auth/verify?token=xxx)

### Offline Support
- Cache accounts, categories, transactions locally
- Queue mutations (new transactions) during offline
- Sync batched changes via `/sync/transactions` when online
- Optimistic updates for instant feedback

### Error Handling
- Network errors → retry with exponential backoff
- 429 (rate limit) → "Please wait" message with countdown
- 400 (validation) → field-specific error messages
- 401 (auth) → redirect to login
- 500 (server) → "Something went wrong" generic message

### Performance
- Paginate transactions (limit=50 per request)
- Cache categories (27 defaults on registration)
- Pre-fetch accounts on app launch
- Poll for notifications (not server-push yet)

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Models** | 18 |
| **Fields documented** | 59 |
| **API endpoints** | 88+ |
| **Validation rules** | 55+ |
| **Edge cases** | 40+ |
| **Rate limit rules** | 3 (IP, email, user) |
| **Test files analyzed** | 40+ |
| **Feature areas** | 16 |
| **Default categories** | 25 |
| **Unique constraints** | 7 |
| **Indexed columns** | 20+ |

## How to Use These Docs

1. **Read in order** → Start with Data Models, then API, then Auth
2. **Reference by feature** → Jump to section in API-SPECIFICATION or BUSINESS-RULES
3. **Copy specs** → Use exact field names, types, validation rules from docs
4. **Implement incrementally** → Start with Dashboard + Auth, then Accounts, then Transactions
5. **Validate against Django** → Running Django backend as reference implementation

## Key Principles

- **Security First** — Every query filters by user_id; no data leaks possible
- **Correctness Over Convenience** — Use Decimal, not floats; atomic transactions
- **User-Centered** — Clear error messages, empty states, loading indicators
- **Offline-Ready** — Batch sync, optimistic updates, queue support
- **Accessible** — ARIA labels, keyboard navigation, focus management
- **Tested** — 55+ validation rules extracted from production tests

## Next Steps

1. Create React Native project with TypeScript
2. Implement Auth (magic link, session management) — see [03-AUTH-SECURITY.md](03-AUTH-SECURITY.md)
3. Implement Data Models (use exact types/fields from [01-DATA-MODELS.md](01-DATA-MODELS.md))
4. Implement API Client (follow contracts in [02-API-SPECIFICATION.md](02-API-SPECIFICATION.md))
5. Implement UI screens (reference layouts in [05-UI-UX-FLOWS.md](05-UI-UX-FLOWS.md))
6. Add business logic validation (rules from [04-BUSINESS-RULES.md](04-BUSINESS-RULES.md))
7. Test against running Django backend (port 8000)

## Files in This Directory

```
docs/mobile/
├── 00-INDEX.md                          ← You are here
├── 01-DATA-MODELS.md                    (18 models, 59 fields, complete specs)
├── 02-API-SPECIFICATION.md              (88+ endpoints, complete contracts)
├── 03-AUTH-SECURITY.md                  (magic link, sessions, rate limiting)
├── 04-BUSINESS-RULES.md                 (validation, edge cases, atomicity)
└── 05-UI-UX-FLOWS.md                    (screens, interactions, mobile patterns)
```

---

**Generated from production codebase analysis on 2026-03-25**
**Dashboard**: Django backend served by Gunicorn on port 8000, run with `DISABLE_RATE_LIMIT=true make run`
**Testing**: Playwright tests in `e2e/` directory with 16 spec files
**Reference**: All source files: `backend/*/models.py`, `backend/*/views.py`, `backend/*/services.py`, `backend/*/tests/`
