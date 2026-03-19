# ClearMoney

Personal finance tracker for managing multi-bank, multi-currency finances in Egypt. Multi-user PWA built with Go + Django, HTMX, Tailwind CSS, and PostgreSQL. Backend is being incrementally migrated from Go to Django using the Strangler Fig pattern.

## What It Does

- **Unified dashboard** — net worth, spending trends, budget progress, and account health at a glance
- **Multi-bank support** — HSBC, CIB, EGBank, Banque Misr, Telda, Fawry, TRU, and more
- **Dual currency** — EGP and USD with exchange rate tracking
- **Transaction entry** — expenses, income, transfers, currency exchanges, batch entry, salary distribution
- **Credit card intelligence** — statement views, billing cycles, utilization tracking, interest-free period alerts
- **Budgets & virtual accounts** — monthly category limits with threshold alerts, envelope-style allocation
- **People tracking** — loan/borrow/repay with debt payoff projections
- **Recurring rules** — auto or manual-confirm recurring transactions
- **Investments & installments** — portfolio tracking, payment plan progress
- **PWA** — installable, offline-capable, push notifications
- **CSS-only charts** — donut, bar, sparkline, and trend charts with no JS libraries

## Quick Start

```bash
# Start PostgreSQL and the app
docker compose up -d --build

# Open in browser
open http://localhost:8080
```

On first visit, enter your email and click the magic link to log in.

### Development (without Docker for the apps)

```bash
docker compose up -d db          # Start PostgreSQL only
make run                         # Start Go dev server on :8080
make django-run                  # Start Django dev server on :8000
```

### Useful Commands

```bash
make test                        # Go unit tests
make test-integration            # Go integration tests (needs running DB)
make django-test                 # Django tests (needs running DB)
make test-e2e                    # Playwright browser tests
make seed                        # Populate sample data
make reconcile                   # Check balance consistency
make logs                        # Stream Docker logs
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Go Backend | Go 1.25, chi v5 router, html/template |
| Django Backend | Django 6.0, django-htmx, gunicorn |
| Database | PostgreSQL 16 (pgx v5 / psycopg3) |
| Migrations | golang-migrate (Go owns schema) |
| Frontend | HTMX + Tailwind CSS (CDN) |
| Auth | Magic link via Resend, DB sessions |
| Charts | CSS-only (conic-gradient, flexbox, inline SVG) |
| Reverse Proxy | Caddy (routes migrated paths to Django) |
| Logging | log/slog (Go), Python logging (Django) |

## Project Structure

```
cmd/                 # Go entry points
  server/            # HTTP server
  seed/              # Sample data seeder
  reconcile/         # Balance verification CLI
internal/            # Go backend (serves all non-migrated routes)
  handler/           # HTTP handlers + routes
  service/           # Business logic
  repository/        # SQL queries
  models/            # Domain structs (no ORM)
  templates/         # Embedded HTML (layouts, pages, partials)
  middleware/        # Auth + request logging
  database/          # Connection pool, migrations (30 migration files)
  ...
backend/             # Django backend (Strangler Fig migration)
  clearmoney/        # Django project settings
  core/              # Shared models (managed=False), auth middleware, template tags
  settings_app/      # Migrated: /settings, /export/transactions
  reports/           # Migrated: /reports
  templates/         # Base layout + components
static/              # CSS, JS, service worker (shared by both backends)
docs/                # Architecture guide, feature docs
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | HTTP server port |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `ENV` | `development` | Environment mode |
| `LOG_LEVEL` | `info` | debug, info, warn, error |
| `VAPID_PUBLIC_KEY` | — | Web Push public key |
| `VAPID_PRIVATE_KEY` | — | Web Push private key |

See `.env.example` for a working local configuration.

## Architecture

**Strangler Fig migration** — Go and Django run side by side, sharing the same PostgreSQL database and session cookie. Caddy routes migrated paths (`/settings`, `/reports`, `/export`) to Django; everything else goes to Go.

```
Go:     HTTP Request → Middleware → Handler → Service → Repository → PostgreSQL
Django: HTTP Request → GoSessionAuthMiddleware → View → raw SQL → PostgreSQL
```

- **Go** serves the majority of routes (dashboard, accounts, transactions, etc.)
- **Django** serves migrated features (settings, reports, CSV export)
- **Schema** owned by Go via golang-migrate — Django uses `managed=False` models
- **Auth** — Go creates session cookies, Django reads them from the same `sessions` table

All monetary values use `NUMERIC(15,2)` in the database. Balance updates are atomic (INSERT transaction + UPDATE balance in a single DB transaction). Each transaction stores a `balance_delta` for reconciliation.

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for Ubuntu VPS deployment with Docker Compose.
