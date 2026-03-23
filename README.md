# ClearMoney

Personal finance tracker for managing multi-bank, multi-currency finances in Egypt. Multi-user PWA built with Django, HTMX, Tailwind CSS, and PostgreSQL.

## What It Does

- **Unified dashboard** — net worth, spending trends, budget progress, and account health at a glance
- **Multi-bank support** — HSBC, CIB, EGBank, Banque Misr, Telda, Fawry, TRU, and more
- **Dual currency** — EGP and USD with exchange rate tracking
- **Transaction entry** — expenses, income, transfers, currency exchanges, batch entry
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
open http://localhost:8000
```

On first visit, enter your email and click the magic link to log in.

### Development (without Docker for the app)

```bash
docker compose up -d db          # Start PostgreSQL only
make run                         # Start Django dev server on :8000
```

### Useful Commands

```bash
make test                        # Django tests (needs running DB)
make test-e2e                    # Playwright browser tests
make lint                        # ruff + mypy
make seed                        # Populate sample data
make reconcile                   # Check balance consistency
make logs                        # Stream Docker logs
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 6.0, django-htmx, gunicorn |
| Database | PostgreSQL 16 (psycopg3) |
| Migrations | Django native (makemigrations / migrate) |
| Frontend | HTMX + Tailwind CSS (CDN) |
| Auth | Magic link via Resend, DB sessions |
| Charts | CSS-only (conic-gradient, flexbox, inline SVG) |
| Reverse Proxy | Caddy (TLS termination) |
| Logging | Python logging |

## Project Structure

```
backend/                  # Django backend
  clearmoney/             # Project settings, URLs, WSGI
  core/                   # Shared models, auth middleware, template tags
  auth_app/               # Login, magic link, logout
  dashboard/              # Home page + HTMX partial loaders
  accounts/               # Accounts + institutions CRUD
  transactions/           # Transactions, transfers, exchanges, batch entry
  people/                 # People + loan tracking
  budgets/                # Budget management
  virtual_accounts/       # Envelope budgeting
  recurring/              # Recurring rules + sync
  investments/            # Investment tracking
  installments/           # Installment/EMI plans
  exchange_rates/         # Exchange rates reference
  categories/             # Category JSON API
  push/                   # Push notification API
  jobs/                   # Background jobs (management commands)
  settings_app/           # Settings page + CSV export
  reports/                # Reports (donut/bar charts)
  templates/              # Shared base.html, header, bottom-nav
static/                   # CSS, JS, service worker, manifest
e2e/                      # Playwright end-to-end tests
docs/                     # Architecture guide, feature docs
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string |
| `ENV` | `development` | Environment mode |
| `LOG_LEVEL` | `info` | debug, info, warn, error |
| `APP_URL` | `http://localhost:8000` | Base URL for magic links |
| `RESEND_API_KEY` | — | Resend API key (logs emails if unset) |
| `VAPID_PUBLIC_KEY` | — | Web Push public key |
| `VAPID_PRIVATE_KEY` | — | Web Push private key |

See `.env.example` for a working local configuration.

## Architecture

```
HTTP Request → Caddy (HTTPS) → Django (gunicorn)
  → WhiteNoiseMiddleware (static files)
  → GoSessionAuthMiddleware (session cookie → user_id)
  → View → raw SQL / ORM → PostgreSQL
  → Template → HTML Response
```

All monetary values use `NUMERIC(15,2)` in the database. Balance updates are atomic (INSERT transaction + UPDATE balance in a single DB transaction). Each transaction stores a `balance_delta` for reconciliation.

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for Ubuntu VPS deployment with Docker Compose.
