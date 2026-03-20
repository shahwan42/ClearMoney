# ClearMoney — AI Assistant Instructions

> Personal finance tracker built with Django, HTMX, Tailwind CSS, and PostgreSQL.
> Multi-user PWA with magic link auth for tracking accounts, transactions, budgets, and investments across Egyptian banks.

## Production App — No Breaking Changes

**This application is live in production with real user data.** Every change MUST be backward-compatible unless the user explicitly states otherwise. This means:

- **Database migrations**: Must be additive only — NO dropping columns, renaming tables, or altering column types that break existing data. Use multi-step migrations (add new → migrate data → drop old) if schema changes are needed.
- **API/Route changes**: Do NOT remove or rename existing endpoints. Add new ones instead.
- **Template changes**: Ensure existing functionality is preserved. Test that all current flows still work.
- **Config/Environment**: Do NOT remove or rename existing env vars. Add new ones with sensible defaults.
- **Dependencies**: Do NOT remove or upgrade dependencies with breaking changes without explicit approval.
- **Data integrity**: Never run destructive operations (DELETE, TRUNCATE, DROP) against production data. All data transformations must be reversible.
- **Default behavior**: If a change could alter existing behavior, it must default to the current behavior unless the user opts in.

When in doubt, ask before making a change that could affect production.

## Developer Profile

- **Name**: Ahmed
- **Background**: PHP Laravel, Python Django, HTMX, PostgreSQL
- **Preferences**: Use Laravel/Django analogies when explaining concepts. Keep comments descriptive but not verbose. Follow DRY principles.

## Quick Start

```bash
docker compose up -d          # Start PostgreSQL (port 5433) + Django app + cron
make run                      # Start Django dev server on :8000
make test                     # Django tests (needs running DB)
make lint                     # Run ruff + mypy
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
  → GoSessionAuthMiddleware (session cookie → user_id)
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

- **Framework**: pytest via `pytest-django` (not `manage.py test`)
- **Plugins**: `pytest-mock` (mocker fixture), `pytest-xdist` (parallel runs with `-n auto`), `pytest-cov` (coverage), `factory_boy` (model factories like Laravel model factories)
- **Run**: `make test` or `cd backend && uv run pytest`
- **Real DB**: Tests run against the real PostgreSQL schema (`--reuse-db` from pytest-django)
- **Fixtures**: Use `factory_boy` factories defined in `tests/factories.py` — like Laravel's `UserFactory::create()`
- **Config**: `backend/pyproject.toml` sets `DJANGO_SETTINGS_MODULE` and `--reuse-db`
- **E2E**: Playwright browser tests in `e2e/` — `make test-e2e`

## General Rules

- **After completing a todo list**, always run the relevant test suites and do a code review before declaring the task done:
  - `make test` (Django tests, requires DB)
  - `make lint` (ruff + mypy)
  - **Code review**: review all changed files for bugs, edge cases, and test gaps — fix issues before declaring done

## Coding Conventions

### Django Style

- **Prefer `pyproject.toml`** for all Python tool configuration (pytest, coverage, mypy, ruff, etc.) over separate config files.
- **Always set `db_table`** in every model's `Meta` class. All models live in `core/models.py`.
- **Write clean, Pythonic code** — use list/dict comprehensions, f-strings, context managers (`with`), and idiomatic patterns. Follow PEP 8.
- **Always add type annotations** to all Python code. Every function must have parameter types and a return type. Use `AuthenticatedRequest` (from `core.types`) instead of `HttpRequest` in views that access `request.user_id` / `request.user_email`. Run `uv run mypy .` from `backend/` to verify — zero errors required.
- **Use pytest** (via `pytest-django`) as the testing framework. Plugins: `pytest-mock`, `pytest-xdist`, `pytest-cov`, `factory_boy`.
- **Document on every level**: module-level docstring → class-level docstring for non-obvious classes → inline comments only where the logic isn't self-evident.

### Commit Message Convention

Use conventional commits: `type: concise description`

- `feat:` new feature — `fix:` bug fix — `refactor:` code restructure — `docs:` documentation
- `chore:` tooling/config — `test:` test additions — keep message under ~72 chars

### Adding a New Feature (TDD: RED → GREEN → Refactor)

Follow strict TDD — write failing tests FIRST, then implement just enough code to make them pass, then refactor.

#### Phase 1: Schema & Models

1. **Migration**: Add/modify models in `core/models.py`, run `make makemigrations`, review generated migration
2. **Apply**: `make migrate`

#### Phase 2: Service (RED → GREEN)

1. **Write service tests FIRST**: Create `<app>/tests/test_services.py` — tests should fail (RED)
2. **Implement service**: Add `<app>/services.py` — make the tests pass (GREEN)

#### Phase 3: View & Templates (RED → GREEN)

1. **Write view tests FIRST**: Create `<app>/tests/test_views.py` — tests should fail (RED)
2. **Implement view**: Add view in `<app>/views.py`, URL in `<app>/urls.py`, templates in `<app>/templates/`

#### Phase 4: E2E & Docs

1. **E2E tests**: Write Playwright browser tests in `e2e/tests/`
2. **Documentation**: Add or update feature doc in `docs/features/`

#### TDD Rules

- **Never skip RED**: Always run the test and confirm it fails before writing implementation code.
- **Minimal GREEN**: Write only enough code to pass the failing test.
- **Refactor after GREEN**: Clean up only after tests are passing.

### Feature Delivery Checklist

1. **Run tests** — `make test`
2. **Run e2e tests** — `make test-e2e`
3. **Run linter** — `make lint`
4. **Code review** — review all changed files for bugs, edge cases, test gaps
5. **Update documentation** — docs/features/ if applicable
6. **Restart the app** — `make run` so the user can try the feature at `http://0.0.0.0:8000`
7. **Show manual test steps** — list the exact UI steps
8. **Wait for approval** — do not proceed until confirmed
9. **Ask to commit** — once approved

### Common Pitfalls

- **Credit card balance signs**: CC balances are stored as negative numbers (representing debt). Display with `neg` template filter when showing "amount used"
- **Category dropdowns**: Use `<optgroup label="Expenses">` and `<optgroup label="Income">`
- **Enum casting in SQL**: When filtering by enum columns (e.g., `currency`), cast the string: `WHERE currency = %s::currency_type`
- **Transaction currency**: Never trust the form's currency field — the service layer overrides it from the account

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

## Dependencies (backend/pyproject.toml)

- `Django==6.0.3` — Web framework
- `psycopg[binary]==3.2.6` — PostgreSQL driver (psycopg3)
- `gunicorn==23.0.0` — Production WSGI server
- `django-htmx==1.27.0` — HTMX integration (request.htmx, HttpResponseClientRedirect)
- `dj-database-url==3.1.0` — DATABASE_URL parsing
- `django-ratelimit==4.1.0` — Rate limiting decorators
- `whitenoise==6.12.0` — Static file serving in production
