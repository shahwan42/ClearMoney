# ClearMoney Documentation Hub

> **Complete reference for all features, architecture, routes, and development patterns.**

Welcome! This directory contains everything you need to understand and extend ClearMoney. Start here, then navigate to specific docs as needed.

---

## 📚 Core References

| Document | Purpose | For Whom |
|----------|---------|----------|
| **[FEATURES.md](FEATURES.md)** | Feature overview: Dashboard, Accounts, Transactions, Reports, Budgets, People, Virtual Accounts, Recurring, Investments, Settings, Auth, PWA | Everyone |
| **[BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md)** | Django backend: 18 models, 14 Django apps, service layer, patterns, middleware, testing, deployment | Backend developers, architects |
| **[ROUTES.md](ROUTES.md)** | Complete route inventory: 125+ routes, HTTP methods, query params, request/response examples | Backend developers, API consumers |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System architecture: request flow, design patterns, tech stack, database schema | Architects, DevOps |
| **[DEPLOYMENT.md](DEPLOYMENT.md)** | Production deployment: Docker, PostgreSQL, Caddy, monitoring, backup, disaster recovery | DevOps, Site Reliability |

---

## 🔧 Feature Documentation

Each feature has a dedicated guide with models, services, views, templates, and common patterns.

### Core Features

| Feature | File | Routes | Models | Purpose |
|---------|------|--------|--------|---------|
| **Dashboard** | [dashboard.md](features/dashboard.md) | `/` | DailySnapshot, AccountSnapshot | Home page aggregation |
| **Accounts & Institutions** | [accounts-and-institutions.md](features/accounts-and-institutions.md) | `/accounts`, `/institutions/*` | Account, Institution | Account & institution management |
| **Transactions** | [transactions.md](features/transactions.md) | `/transactions`, `/transfers`, `/exchange`, `/batch-entry` | Transaction, Person | All transaction types |
| **Reports** | [reports.md](features/reports.md) | `/reports` | DailySnapshot | Monthly spending analysis |
| **Budgets** | [budgets.md](features/budgets.md) | `/budgets` | Budget, TotalBudget | Monthly spending limits |
| **People** | [people.md](features/people.md) | `/people` | Person | Loan & debt tracking |
| **Virtual Accounts** | [virtual-accounts.md](features/virtual-accounts.md) | `/virtual-accounts` | VirtualAccount, VirtualAccountAllocation | Envelope budgeting |
| **Credit Cards** | [credit-cards.md](features/credit-cards.md) | `/accounts/<id>/statement` | Account (type=cc) | CC management & utilization |
| **Recurring Rules** | [recurring-rules.md](features/recurring-rules.md) | `/recurring` | RecurringRule | Scheduled transactions |
| **Investments** | [investments.md](features/investments.md) | `/investments` | Investment | Portfolio tracking |

### Cross-Cutting Features

| Feature | File | Routes | Purpose |
|---------|------|--------|---------|
| **Authentication** | [auth.md](features/auth.md) | `/login`, `/auth/verify`, `/logout`, `/api/session-status` | Magic link auth, session management |
| **Settings** | [settings.md](features/settings.md) | `/settings`, `/settings/categories`, `/export/transactions` | Preferences, category CRUD, CSV export |
| **Exchange Rates** | [exchange-rates.md](features/exchange-rates.md) | - | Historical rates, multi-currency support |
| **Charts** | [charts.md](features/charts.md) | - | CSS-only donut, bar, sparkline implementation |
| **Bottom Sheet** | [bottom-sheet.md](features/bottom-sheet.md) | - | Reusable slide-up component |
| **PWA** | [pwa.md](features/pwa.md) | - | Manifest, service worker, push notifications, offline |
| **Rate Limiting** | [rate-limiting.md](features/rate-limiting.md) | - | Per-user rate limits, anti-bot |
| **Logging** | [logging.md](features/logging.md) | - | Structured logging, event tracking |

---

## 🔍 QA & Planning

Work tracking has been consolidated into a single AI-managed ticketing system.

See [`.tickets/`](../.tickets/) for all development tasks:
- **Done** — completed features, fixes, audits
- **In Progress** — active work
- **Pending** — backlog
- **Rejected** — cancelled or discarded plans

All historical QA findings and improvements are tracked as tickets in `.tickets/done/` and automatically indexed in [`.tickets/INDEX.md`](./.tickets/INDEX.md).

---

## 🚀 Quick Start for Developers

### Prerequisites
```bash
# Install dependencies (uv workspace: backend + e2e)
uv sync

# Environment setup
cp .env.example .env
# Edit .env with your database URL, API keys, etc.

# Database
make migrate

# Tests
make test  # 1130+ tests should pass
```

### Development Workflow
```bash
# Start server (rate limiting disabled for testing)
DISABLE_RATE_LIMIT=true make run

# Run tests
make test
make test-e2e
make lint
```

### Adding a New Feature
Follow TDD (RED → GREEN → Refactor):
1. **Model**: Add to `backend/core/models.py`, create migration
2. **Tests**: Write failing tests in `<app>/tests/test_services.py`
3. **Service**: Implement business logic in `<app>/services.py`
4. **Views**: Add routes in `<app>/views.py`
5. **Templates**: Create templates in `<app>/templates/`
6. **URL**: Register routes in `<app>/urls.py`
7. **Test**: `make test && make lint`
8. **Docs**: Update `docs/features/<feature>.md`

---

## 📊 Project Statistics

- **Backend**: 14 Django apps, 18 models, 125+ routes
- **Testing**: 1129+ unit/integration tests, 16 Playwright e2e specs
- **Documentation**: 37+ markdown files covering all features
- **Code Quality**: 100% type annotations (mypy), linted (ruff)
- **Deployment**: Docker, PostgreSQL, Caddy, Hetzner VPS

---

## 🏗️ Architecture at a Glance

```
HTTP Request
    ↓
Caddy (reverse proxy, TLS)
    ↓
Django (gunicorn)
    ↓
WhiteNoise (static files)
    ↓
GoSessionAuthMiddleware (auth validation)
    ↓
View (thin, delegates to service)
    ↓
Service (business logic, atomic transactions)
    ↓
ORM (models with per-user scoping)
    ↓
PostgreSQL (JSONB, materialized views)
    ↓
Response (template or JSON)
```

**Key patterns:**
- Service layer handles all business logic
- Per-user data isolation (WHERE user_id = %)
- Atomic database transactions
- HTMX for partial updates (no full-page refreshes)
- CSS-only charts (no Chart.js)
- Magic link auth (no passwords)

---

## 🔑 Key Files

| File | Purpose |
|------|---------|
| `pyproject.toml` (root) | uv workspace config (members: backend, e2e) |
| `backend/pyproject.toml` | Backend dependencies, pytest config, mypy config, ruff rules |
| `e2e/pyproject.toml` | E2E dependencies, pytest config for Playwright |
| `uv.lock` (root) | Unified lockfile for all dependencies |
| `backend/core/models.py` | All 14 Django models (User, Account, Transaction, etc.) |
| `backend/core/types.py` | `AuthenticatedRequest` type with user_id, user_email |
| `backend/core/middleware.py` | `GoSessionAuthMiddleware` for session validation |
| `backend/core/templatetags/money.py` | Template filters: format_egp, format_usd, neg, percentage, chart colors |
| `backend/clearmoney/urls.py` | Main URL configuration |
| `backend/clearmoney/settings.py` | Django settings |
| `backend/tests/factories.py` | factory_boy fixtures for testing |
| `backend/tests/conftest.py` | pytest fixtures (auth_user, auth_client, etc.) |
| `Makefile` | Commands: make run, make test, make migrate, etc. |
| `.env.example` | Environment variable template |

---

## 📖 Common Tasks

### I want to...

**...add a new account type (e.g., "Money Market")**
→ [accounts-and-institutions.md](features/accounts-and-institutions.md) → Modify `Account.type` enum → Add tests

**...add a new category**
→ [settings.md](features/settings.md) → Check `categories/services.py`

**...add a new budget constraint**
→ [budgets.md](features/budgets.md) → Modify `Budget` model

**...add a new report type**
→ [reports.md](features/reports.md) → Extend `reports/services.py`

**...fix a transaction bug**
→ [transactions.md](features/transactions.md) → Check `transactions/services.py` and tests

**...improve mobile UX**
→ [research/UX_MOBILE_RESPONSIVENESS.md](research/UX_MOBILE_RESPONSIVENESS.md) → Check touch targets, spacing

**...add dark mode support**
→ [research/UX_SETTINGS_DARK_MODE.md](research/UX_SETTINGS_DARK_MODE.md) → Dark mode is already implemented, see how it works

**...add a new chart type**
→ [charts.md](features/charts.md) → CSS conic-gradient or flexbox implementation

**...understand the auth flow**
→ [auth.md](features/auth.md) → Magic link via Resend, session storage in DB

**...deploy to production**
→ [DEPLOYMENT.md](DEPLOYMENT.md) → Docker, PostgreSQL, Caddy setup

---

## 🔗 Related Documentation

- **Git**: See `.git/` for commit history (use `git log` to understand decisions)
- **Rules**: See `.claude/rules/` for production safety, accessibility, TDD, coding conventions
- **Codebase instructions**: See `CLAUDE.md` for project-specific guidelines

---

## 📞 Support

- **Questions about features?** Start with the feature doc (e.g., [transactions.md](features/transactions.md))
- **Questions about architecture?** Check [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md)
- **Questions about routes?** See [ROUTES.md](ROUTES.md)
- **Questions about UX?** See [research/](research/)
- **Questions about deployment?** See [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 📋 Documentation Maintenance

This documentation is version-controlled. When you:
- **Add a feature**: Update the relevant feature doc + this index
- **Change an API route**: Update [ROUTES.md](ROUTES.md)
- **Refactor a service**: Update the feature doc's "Service" section
- **Identify a UX issue**: Add to [research/UX_FINDINGS_SUMMARY.md](research/UX_FINDINGS_SUMMARY.md)

---

## 🎯 Next Steps

1. **Read [FEATURES.md](FEATURES.md)** for a 5-minute feature overview
2. **Read [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md)** for system design
3. **Pick a feature** from the list above and read its dedicated doc
4. **Run `make test`** to ensure everything works
5. **Start building!**

---

**Last updated:** 2026-03-25 | **Docs version:** 2.0 (comprehensive, 37+ files)
