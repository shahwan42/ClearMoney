# ClearMoney

Personal finance tracker for managing multi-bank, multi-currency finances in Egypt. Single-user PWA built with Go, HTMX, Tailwind CSS, and PostgreSQL.

## What It Does

- **Unified dashboard** — net worth, spending trends, budget progress, and account health at a glance
- **Multi-bank support** — HSBC, CIB, EGBank, Banque Misr, Telda, Fawry, TRU, and more
- **Dual currency** — EGP and USD with exchange rate tracking
- **Transaction entry** — expenses, income, transfers, currency exchanges, batch entry, salary distribution
- **Credit card intelligence** — statement views, billing cycles, utilization tracking, interest-free period alerts
- **Budgets & virtual funds** — monthly category limits with threshold alerts, envelope-style fund allocation
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

On first visit, you'll be prompted to create a PIN. That's it.

### Development (without Docker for the app)

```bash
docker compose up -d db          # Start PostgreSQL only
make run                         # Start dev server on :8080
```

### Useful Commands

```bash
make test                        # Unit tests
make test-integration            # Integration tests (needs running DB)
make seed                        # Populate sample data
make reconcile                   # Check balance consistency
make logs                        # Stream Docker logs
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Go 1.25 |
| Router | chi v5 |
| Database | PostgreSQL 16 (pgx v5 driver) |
| Migrations | golang-migrate (embedded SQL) |
| Templates | Go html/template |
| Frontend | HTMX + Tailwind CSS (CDN) |
| Auth | PIN-based, bcrypt + HMAC sessions |
| Charts | CSS-only (conic-gradient, flexbox, inline SVG) |
| Logging | log/slog (structured) |

## Project Structure

```
cmd/
  server/          # HTTP server entry point
  seed/            # Sample data seeder
  reconcile/       # Balance verification CLI
internal/
  config/          # Environment-based configuration
  database/        # Connection pool, migrations (18 migration files)
  handler/         # HTTP handlers + routes
  jobs/            # Background tasks (reconcile, snapshots, views)
  middleware/      # Auth + request logging
  models/          # Domain structs (no ORM)
  repository/      # SQL queries
  service/         # Business logic
  templates/       # Embedded HTML (layouts, pages, partials)
  testutil/        # Test DB helpers + fixture factories
static/            # CSS, JS, service worker, PWA manifest
docs/              # Architecture guide, Go cheatsheet
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

```
HTTP Request → Middleware (auth + logging) → Handler → Service → Repository → PostgreSQL
```

- **Handlers** parse HTTP requests, call services, render templates or JSON
- **Services** contain business logic, orchestrate repositories
- **Repositories** execute raw SQL, return model structs
- **Models** are plain structs with `json`/`db` tags — no ORM

All monetary values use `NUMERIC(15,2)` in the database. Balance updates are atomic (INSERT transaction + UPDATE balance in a single DB transaction). Each transaction stores a `balance_delta` for reconciliation.

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for Ubuntu VPS deployment with Docker Compose.
