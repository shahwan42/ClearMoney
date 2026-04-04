---
id: "113"
title: "Django Admin setup for monitoring and management"
type: feature
priority: high
status: wip
created: 2026-04-04
updated: 2026-04-04
---

## Description

Enable Django Admin at `/admin` for monitoring, managing, and tracking user data and behavior. The project currently has no admin — `django.contrib.admin`, `django.contrib.auth`, `django.contrib.contenttypes`, and `django.contrib.sessions` are all absent. The custom User model (magic link, no password) means we need Django's built-in auth system *only* for admin access, while keeping the existing magic link flow for regular users.

## Why

- No way to inspect user data, transactions, balances, or sessions without raw SQL
- Need visibility into user behavior (sign-ups, activity, spending patterns)
- Need ability to manage data (fix balances, clean up test accounts, deactivate users)
- Admin is the standard Django tool for this — no need to build custom dashboards

## Challenges

1. **No `django.contrib.auth`** — the project uses a custom `auth_app.User` model (UUID PK, no password field, no `is_staff`/`is_superuser`). Django Admin requires `django.contrib.auth.models.User` or a custom user model that implements `AbstractBaseUser`.
2. **No `django.contrib.contenttypes`** — required by admin for permissions/log entries.
3. **No `django.contrib.sessions`** — admin needs Django's session backend for its own login. The project uses a custom `sessions` table via `GoSessionAuthMiddleware`.
4. **Middleware conflict** — `GoSessionAuthMiddleware` will intercept `/admin` requests and redirect to `/login` (magic link). Admin must be excluded from this middleware.
5. **No password on User model** — need to either (a) add a password field to the existing User model, or (b) create a separate Django auth user for admin access.

## Approach

**Option A (Recommended): Add Django's auth User model alongside existing User model.**

- Install `django.contrib.admin`, `django.contrib.auth`, `django.contrib.contenttypes`, `django.contrib.sessions`
- Django's `auth.User` lives in its own `auth_user` table — completely separate from the `users` table
- Create a superuser via `manage.py createsuperuser` for admin login
- Admin uses Django's built-in session backend (`django_session` table) — separate from the custom `sessions` table
- Exclude `/admin` from `GoSessionAuthMiddleware`
- Register all 18 app models (21 total minus 3 empty) with rich admin configs

**Why not Option B (make auth_app.User extend AbstractBaseUser)?**
- Requires adding `password`, `is_staff`, `is_superuser`, `last_login` fields to the `users` table
- Breaking change to a production table with real data
- Mixes admin concerns into the app's user model
- The custom User model is intentionally minimal (magic link only)

## Implementation Plan

### Step 1: Install Django contrib apps + middleware

**settings.py changes:**
- Add to `INSTALLED_APPS`: `django.contrib.admin`, `django.contrib.auth`, `django.contrib.contenttypes`, `django.contrib.sessions`
- Add `django.contrib.sessions.middleware.SessionMiddleware` to `MIDDLEWARE` (before `CommonMiddleware`)
- Add `django.contrib.auth.middleware.AuthenticationMiddleware` to `MIDDLEWARE` (after `SessionMiddleware`)
- Add `django.contrib.messages` + `django.contrib.messages.middleware.MessageMiddleware` (admin needs it)
- Add `django.template.context_processors.messages` to template context processors (admin needs it)
- Update settings docstring to reflect admin is now included

### Step 2: Exclude `/admin` from GoSessionAuthMiddleware

**core/middleware.py change:**
- Add `"/admin"` to the public paths list so the middleware skips admin URLs
- Admin uses its own auth (Django's built-in), not magic links

### Step 3: Run migrations for contrib apps

```bash
make migrate
```

This creates: `auth_user`, `auth_group`, `auth_permission`, `django_content_type`, `django_session`, `django_admin_log` tables. No changes to existing tables.

### Step 4: Register admin URL

**clearmoney/urls.py:**
```python
from django.contrib import admin
urlpatterns = [
    path("admin/", admin.site.urls),
    # ... existing patterns
]
```

### Step 5: Create superuser management command or use built-in

```bash
cd backend && uv run manage.py createsuperuser
```

### Step 6: Register all models with admin

Create `admin.py` in each app with rich configurations:

**auth_app/admin.py** — User, Session, AuthToken, DailySnapshot
- `UserAdmin`: list_display (email, created_at, transaction count), search by email, readonly created_at
- `SessionAdmin`: list_display (user email, expires_at, created_at), filter by active/expired
- `AuthTokenAdmin`: list_display (email, purpose, used, expires_at), filter by purpose/used
- `DailySnapshotAdmin`: list_display (user, date, net_worth_egp, daily_spending, daily_income), date filter

**accounts/admin.py** — Institution, Account, AccountSnapshot
- `InstitutionAdmin`: list_display (name, type, user, account count), search by name
- `AccountAdmin`: list_display (name, type, currency, current_balance, institution, is_dormant), filter by type/currency/is_dormant, search by name
- `AccountSnapshotAdmin`: list_display (account, date, balance), date filter, readonly

**transactions/admin.py** — Transaction, VirtualAccountAllocation
- `TransactionAdmin`: list_display (date, type, amount, currency, account, category, note), filter by type/currency/date, search by note, readonly balance_delta
- `VirtualAccountAllocationAdmin`: list_display (virtual_account, amount, allocated_at)

**categories/admin.py** — Category
- `CategoryAdmin`: list_display (name, type, icon, is_system, is_archived, display_order), filter by type/is_system/is_archived

**budgets/admin.py** — Budget, TotalBudget
- `BudgetAdmin`: list_display (user, category, monthly_limit, currency, is_active), filter by currency/is_active
- `TotalBudgetAdmin`: list_display (user, monthly_limit, currency, is_active)

**people/admin.py** — Person
- `PersonAdmin`: list_display (name, user, net_balance, net_balance_egp, net_balance_usd), search by name

**virtual_accounts/admin.py** — VirtualAccount
- `VirtualAccountAdmin`: list_display (name, user, target_amount, current_balance, is_archived), filter by is_archived

**recurring/admin.py** — RecurringRule
- `RecurringRuleAdmin`: list_display (user, frequency, day_of_month, next_due_date, is_active, auto_confirm), filter by frequency/is_active

**investments/admin.py** — Investment
- `InvestmentAdmin`: list_display (platform, fund_name, units, last_unit_price, currency, user), filter by currency/platform

**exchange_rates/admin.py** — ExchangeRateLog
- `ExchangeRateLogAdmin`: list_display (date, rate, source, note), date filter, search by source/note

### Step 7: Admin site customization

- Set `admin.site.site_header = "ClearMoney Admin"`
- Set `admin.site.site_title = "ClearMoney"`
- Set `admin.site.index_title = "Dashboard"`

### Step 8: Tests

- Test admin URL returns 200 (login page) for unauthenticated
- Test admin URL returns 200 (dashboard) for superuser
- Test GoSessionAuthMiddleware skips `/admin` paths
- Test all model admins are registered (iterate `admin.site._registry`)

### Step 9: Production deployment

- Add `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` env vars for production
- Run `manage.py createsuperuser --noinput` in deploy script (idempotent)
- Consider restricting `/admin` to specific IPs via Caddy (optional, future)

## Acceptance Criteria

- [ ] `/admin` loads Django Admin login page
- [ ] Superuser can log in and see all registered models
- [ ] All 18 models registered with useful list_display, filters, and search
- [ ] GoSessionAuthMiddleware does NOT intercept `/admin` requests
- [ ] Existing magic link auth flow unchanged (no regression)
- [ ] No changes to existing `users` table schema
- [ ] New Django contrib tables created via migration (non-destructive)
- [ ] `make test` passes (no regressions)
- [ ] `make lint` passes (zero errors)
- [ ] Admin is read-heavy by default (most fields readonly where mutation is risky)

## Risks

- **Migration on production DB**: `migrate` adds new tables only — no changes to existing tables. Safe.
- **Middleware ordering**: `SessionMiddleware` must come before `AuthenticationMiddleware`. Standard Django ordering.
- **Two auth systems**: Django's auth (admin only) + magic links (app users). Clear separation, no conflict.

## Progress Notes

- 2026-04-04: Started — Ticket planning, explored codebase state (no admin.py files, no contrib apps installed)
