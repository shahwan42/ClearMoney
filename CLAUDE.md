# ClearMoney — AI Assistant Instructions

> Personal finance tracker built with Django, HTMX, Tailwind CSS, and PostgreSQL.
> Multi-user PWA with magic link auth for tracking accounts, transactions, budgets, and investments across Egyptian banks.

## Production App — No Breaking Changes

**This application is live in production with real user data.** Every change MUST be backward-compatible unless the user explicitly states otherwise. This means:

- **Database migrations**: Additive only — NO dropping columns, renaming tables, or altering column types that break existing data. Use multi-step migrations (add new → migrate data → drop old) if schema changes are needed.
- **API/Route changes**: Do NOT remove or rename existing endpoints. Add new ones instead.
- **Config/Environment**: Do NOT remove or rename existing env vars. Add new ones with sensible defaults.
- **Dependencies**: Do NOT remove or upgrade dependencies with breaking changes without explicit approval.
- **Data integrity**: Never run destructive operations (DELETE, TRUNCATE, DROP) against production data.
- **Default behavior**: Changes that alter existing behavior must default to the current behavior unless the user opts in.

When in doubt, ask before making a change that could affect production.

## Developer Profile

- **Name**: Ahmed
- **Background**: PHP Laravel, Python Django, HTMX, PostgreSQL
- **Toolchain**: `uv` for Python package management, `make` for task shortcuts
- **Preferences**: Use Laravel/Django analogies when explaining concepts. Keep comments descriptive but not verbose. Follow DRY principles.

## Quick Start

```bash
docker compose up -d          # Start PostgreSQL (port 5433) + Django app + cron
make run                      # Start Django dev server on :8000
make test                     # Django tests (needs running DB) — uses uv run pytest
make lint                     # Run ruff + mypy — uses uv run
make test-e2e                 # Playwright browser tests
make reconcile                # Check balance consistency
make makemigrations           # Generate Django migrations
make migrate                  # Apply pending migrations
```

## Architecture

```text
backend/                  # Django backend (sole backend)
  clearmoney/             # Django project settings, URLs, WSGI
  core/                   # Shared: models, auth middleware, template tags
  auth_app/               # Login, register, magic link, logout
  dashboard/              # Home page + HTMX partial loaders
  accounts/               # Accounts + institutions CRUD
  transactions/           # Transactions, transfers, exchanges, batch entry
  people/                 # People + loan tracking
  budgets/                # Budget management
  virtual_accounts/       # Envelope budgeting
  recurring/              # Recurring rules + sync
  salary/                 # Salary wizard
  investments/            # Investment tracking
  installments/           # Installment/EMI plans
  exchange_rates/         # Exchange rates reference page
  categories/             # Category JSON API
  push/                   # Push notification API
  jobs/                   # Background jobs (management commands)
  settings_app/           # Settings page + CSV export
  reports/                # Reports (donut/bar charts)
  templates/              # Shared base.html, header, bottom-nav
static/                   # CSS, JS, service worker, manifest (served by whitenoise)
e2e/                      # Playwright end-to-end tests
```

### Request Flow

```text
HTTP Request → Caddy (HTTPS) → Django (gunicorn)
  → WhiteNoiseMiddleware (static files)
  → GoSessionAuthMiddleware (session cookie → user_id)  # legacy name from Go migration
  → View → raw SQL / ORM → PostgreSQL
  → Template → HTML Response
```

### Key Design Patterns

| Pattern | Details |
| ------- | ------- |
| Auth | Magic link via Resend, server-side DB sessions, per-user data isolation |
| Balance tracking | Atomic updates via DB transactions, `balance_delta` per transaction for reconciliation |
| Charts | CSS-only (conic-gradient donuts, flexbox bars, inline SVG sparklines) — no Chart.js |
| Frontend | HTMX for dynamic updates, Tailwind CSS via CDN, dark mode (class-based) |
| Static files | whitenoise middleware serves CSS/JS/icons in production |
| Monetary values | `NUMERIC(15,2)` in DB, `Decimal` in Python |

## Database

- **Driver**: psycopg3 via `dj-database-url`
- **Migrations**: Django native (`make makemigrations` / `make migrate`). All models in `core/models.py`.
- **Materialized views**: `mv_monthly_category_totals`, `mv_daily_tx_counts`
- **Connection**: `DATABASE_URL` env var, port `5433` (Colima, not 5432)

## Testing

- **Framework**: pytest via `pytest-django` (not `manage.py test`) — run with `uv run pytest`
- **Plugins**: `pytest-mock` (mocker fixture), `pytest-xdist` (parallel with `-n auto`), `pytest-cov` (coverage), `factory_boy` (model factories like Laravel model factories)
- **Real DB**: Tests run against the real PostgreSQL schema (`--reuse-db` from pytest-django)
- **Fixtures**: `factory_boy` factories in `tests/factories.py`; `conftest.py` provides `auth_user`, `auth_cookie`, `auth_client`
- **Config**: `backend/pyproject.toml` sets `DJANGO_SETTINGS_MODULE` and `--reuse-db`
- **E2E**: Playwright browser tests in `e2e/` — `make test-e2e`

## Coding Conventions

**After completing a task**, always run tests and do a code review before declaring done:

- `make test` (Django unit tests)
- `make lint` (ruff + mypy — zero errors required)
- Code review: check all changed files for bugs, edge cases, test gaps

### Django Style

- **Prefer `pyproject.toml`** for all Python tool configuration (pytest, coverage, mypy, ruff, etc.).
- **Always set `db_table`** in every model's `Meta` class. All models live in `core/models.py`.
- **Write clean, Pythonic code** — list/dict comprehensions, f-strings, context managers, PEP 8.
- **Always add type annotations** — every function needs parameter types and return type. Use `AuthenticatedRequest` (from `core.types`) instead of `HttpRequest` in views — it adds `user_id: str`, `user_email: str`, and `tz: zoneinfo.ZoneInfo`. Run `uv run mypy .` from `backend/` to verify — zero errors required.
- **Document on every level**: module-level docstring → class-level for non-obvious classes → inline comments only where logic isn't self-evident.

### Commit Message Convention

Use conventional commits: `type: concise description` (under ~72 chars)

- `feat:` new feature — `fix:` bug fix — `refactor:` code restructure — `docs:` documentation — `chore:` tooling/config — `test:` test additions

### Adding a New Feature (TDD: RED → GREEN → Refactor)

Follow strict TDD — write failing tests FIRST, then implement just enough to pass, then refactor. **Never skip RED**: always run the test and confirm it fails before writing implementation.

1. **Schema & Models**: Add/modify models in `core/models.py` → `make makemigrations` → review migration → `make migrate`
2. **Service (RED → GREEN)**: Write failing tests in `<app>/tests/test_services.py` first, then implement `<app>/services.py`
3. **View & Templates (RED → GREEN)**: Write failing tests in `<app>/tests/test_views.py` first, then implement view, URL, and templates
4. **E2E & Docs**: Write Playwright tests in `e2e/tests/`; add/update docs in `docs/features/`

### Feature Delivery Checklist

1. **Run tests** — `make test`
2. **Run e2e + lint** — `make test-e2e && make lint`
3. **Code review** — check all changed files for bugs, edge cases, test gaps
4. **Update documentation** — `docs/features/` if applicable
5. **Restart the app** — `make run` so the user can try it at `http://0.0.0.0:8000`
6. **Show manual test steps** — list the exact UI steps
7. **Ask to commit** — once approved

### Common Pitfalls

- **Credit card balance signs**: CC balances are stored as negative numbers (representing debt). Display with `neg` template filter when showing "amount used"
- **Category dropdowns**: Use `<optgroup label="Expenses">` and `<optgroup label="Income">`
- **Enum casting in SQL**: When filtering by enum columns (e.g., `currency`), cast the string: `WHERE currency = %s::currency_type`
- **Transaction currency**: Never trust the form's currency field — the service layer overrides it from the account

### ARIA Accessibility Standards

All new and modified templates/JS MUST follow these rules:

- **Dialogs/modals**: `role="dialog"`, `aria-modal="true"`, `aria-labelledby` → title, focus trap on open, restore focus on close
- **Dropdowns**: `aria-haspopup="menu"` + `aria-expanded` on trigger; `role="menu"` on container; `role="menuitem"` on items; arrow key navigation
- **Toggles**: `aria-pressed` or `role="switch"` + `aria-checked`; active nav items: `aria-current="page"`
- **HTMX targets**: `aria-live="polite"` for updates, `"assertive"` for errors; `aria-busy="true"` during loading
- **Forms**: every input needs `<label for="">` or `aria-label`; errors use `role="alert"` + `aria-describedby`; invalid fields: `aria-invalid="true"`; radio groups: `<fieldset>` + `<legend>`
- **Icon-only buttons**: must have `aria-label`
- **CSS charts**: `aria-label` with data summary or visually-hidden data table; SVG charts: `<title>`, `<desc>`, `role="img"`
- **Touch gestures** (swipe-to-delete, pull-to-refresh): always provide a keyboard/button alternative
- **Page structure**: `<html lang="en">`, skip-to-content link, semantic landmarks (`<main>`, `<nav aria-label="...">`, etc.), toast container: `aria-live="polite"` + `aria-atomic="true"`

### Startup Sequence (Background Jobs)

`run_startup_jobs` management command runs: cleanup_sessions → process_recurring → reconcile_balances → refresh_views → take_snapshots

## Environment Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `DATABASE_URL` | (none) | PostgreSQL connection string |
| `ENV` | `development` | Environment mode |
| `LOG_LEVEL` | `info` | Logging level: debug, info, warn, error |
| `APP_TIMEZONE` | `Africa/Cairo` | User timezone for date display and calendar logic |
| `RESEND_API_KEY` | (none) | Resend API key (dev mode if unset — logs emails) |
| `EMAIL_FROM` | `noreply@clearmoney.app` | Verified sender address for magic links |
| `APP_URL` | `http://localhost:8000` | Base URL for magic links in emails |
| `MAX_DAILY_EMAILS` | `50` | Global daily email cap (Resend free tier buffer) |
| `VAPID_PUBLIC_KEY` | (none) | Web Push VAPID public key |
| `VAPID_PRIVATE_KEY` | (none) | Web Push VAPID private key |
| `DISABLE_RATE_LIMIT` | (none) | Set to `true` to skip rate limiting (e2e tests) |
| `DJANGO_SECRET_KEY` | (insecure default) | Django secret key (must set in production) |
| `DJANGO_ALLOWED_HOSTS` | `localhost,0.0.0.0,127.0.0.1` | Comma-separated allowed hosts |

## Dependencies

See `backend/pyproject.toml` for pinned versions.

- `Django` — Web framework
- `psycopg[binary]` — PostgreSQL driver (psycopg3)
- `gunicorn` — Production WSGI server
- `django-htmx` — HTMX integration (`request.htmx`, `HttpResponseClientRedirect`)
- `dj-database-url` — `DATABASE_URL` parsing
- `django-ratelimit` — Rate limiting decorators
- `whitenoise` — Static file serving in production
