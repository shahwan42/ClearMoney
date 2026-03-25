# ClearMoney — AI Assistant Instructions

> Personal finance tracker: Django, HTMX, Tailwind CSS, PostgreSQL. Multi-user PWA with magic link auth.

## Reference Files

| What | Where |
| ---- | ----- |
| Commands | `Makefile` — `make run`, `make test`, `make lint`, etc. |
| Config | `backend/pyproject.toml` — deps, pytest, ruff, mypy, coverage |
| Env vars | `.env.example` |
| Models | `backend/core/models.py` — all models, `db_table` convention |
| Request type | `backend/core/types.py` — `AuthenticatedRequest` |
| Template filters | `backend/core/templatetags/money.py` |
| Rules | `.claude/rules/` — production safety, coding conventions, TDD, delivery checklist, accessibility, pitfalls, auth flow, batch execution, accessibility QA |
| Workflows | `.claude/rules/batch-execution-pattern.md` — multi-item batch workflows; `docs/reference/WCAG-AA-QUICK-REFERENCE.md` — WCAG 2.1 AA criteria & fixes |
| Accessibility | `.claude/rules/accessibility.md` — ARIA standards; `.claude/rules/accessibility-qa-protocol.md` — QA verification gates |

## Architecture

```text
backend/                  # Django backend (sole backend)
  clearmoney/             # Settings, URLs, WSGI
  core/                   # Models, auth middleware, template tags, types
  auth_app/               # Magic link auth
  dashboard/              # Home + HTMX partial loaders
  accounts/               # Accounts + institutions CRUD
  transactions/           # Transactions, transfers, exchanges, batch entry
  people/                 # People + loan tracking
  budgets/                # Budget management
  virtual_accounts/       # Envelope budgeting
  recurring/              # Recurring rules + sync
  investments/            # Investment tracking
  exchange_rates/         # Exchange rates reference
  categories/             # Category JSON API
  push/                   # Push notification API
  jobs/                   # Background jobs (management commands)
  settings_app/           # Settings + CSV export
  reports/                # Reports (donut/bar charts)
  templates/              # Shared base.html, header, bottom-nav
static/                   # CSS, JS, service worker, manifest
e2e/                      # Playwright end-to-end tests
```

### Request Flow

```text
HTTP → Caddy → Django (gunicorn) → WhiteNoise → GoSessionAuthMiddleware → View → ORM → PostgreSQL → Template → HTML
```

### Key Design Patterns

| Pattern | Details |
| ------- | ------- |
| Auth | Magic link via Resend, DB sessions, per-user data isolation |
| Balance tracking | Atomic DB transactions, `balance_delta` per transaction for reconciliation |
| Charts | CSS-only (conic-gradient donuts, flexbox bars, SVG sparklines) — no Chart.js |
| Frontend | HTMX + Tailwind CSS via CDN, dark mode (class-based) |
| Static files | whitenoise in production |
| Monetary values | `NUMERIC(15,2)` in DB, `Decimal` in Python |

### Database Notes

- Materialized views: `mv_monthly_category_totals`, `mv_daily_tx_counts`
- Startup jobs (`run_startup_jobs`): cleanup_sessions → process_recurring → reconcile_balances → refresh_views → take_snapshots
