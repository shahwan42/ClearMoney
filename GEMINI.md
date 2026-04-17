# ClearMoney — AI Assistant Instructions

> Personal finance tracker: Django, HTMX, Tailwind CSS, PostgreSQL. Multi-user PWA with magic link auth.

## Reference Files

| What | Where |
| ---- | ----- |
| Commands | `Makefile` — `make run`, `make test`, `make lint`, etc. |
| Dependencies | `pyproject.toml` (root) — uv workspace config; `backend/pyproject.toml` and `e2e/pyproject.toml` — per-project deps; `uv.lock` (root) — unified lockfile |
| Config | `backend/pyproject.toml` — pytest, ruff, mypy, coverage; `e2e/pyproject.toml` — pytest config for Playwright |
| Env vars | `.env.example` |
| Models | `backend/core/models.py` — all models, `db_table` convention |
| Request type | `backend/core/types.py` — `AuthenticatedRequest` |
| Template filters | `backend/core/templatetags/money.py` |
| Rules | `.gemini/rules/` — ticket-first, git workflow, production safety, coding conventions, TDD, delivery checklist, accessibility, pitfalls, auth flow, batch execution, accessibility QA, QA guidelines, critical paths, ticketing workflow |
| Ticketing | `.tickets/` + `.gemini/rules/ticketing-workflow.md` (mechanics) + `.gemini/rules/ticket-first-workflow.md` (mandatory pre-code gate) — AI-managed development tickets, auto-created/updated by Gemini |
| Workflows | `.gemini/rules/batch-execution-pattern.md` — multi-item batch workflows; `docs/reference/WCAG-AA-QUICK-REFERENCE.md` — WCAG 2.1 AA criteria & fixes |
| Accessibility | `.gemini/rules/accessibility.md` — ARIA standards; `.gemini/rules/accessibility-qa-protocol.md` — QA verification gates |
| QA Guidelines | `.gemini/rules/qa-guidelines.md` — test pyramid, financial data integrity, coverage floors, E2E requirements, form validation standards |
| Critical Paths | `.gemini/rules/critical-paths.md` — 6 critical user journeys that must always pass, regression checkpoints |
| Test Flows | `docs/qa/TEST-FLOWS.md` — detailed test scenarios for all 14 feature areas, known gaps |
| QA Engineer Guide | `docs/qa/QA-ENGINEER-GUIDE.md` — manual QA setup, make commands, test data baseline, bug filing, known issues |
| Remote setup | `.gemini/rules/remote-environment.md` — remote vs local DB differences, SessionStart hook |

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

### LSP Features

The agent uses `basedpyright-langserver` for code intelligence via a singleton
LSP client (`core.lsp_client`):

```python
from core.lsp_client import basedpyright

# Jump to definition (0-indexed line/col)
loc = basedpyright.goto_definition("core/models.py", line=10, col=0)

# Get hover info (type hints, docstrings)
hover = basedpyright.hover("core/models.py", line=10, col=0)

# Find all references to a symbol
refs = basedpyright.find_references("core/models.py", line=10, col=0)

# Get diagnostics (errors/warnings) for a file
diags = basedpyright.diagnostics("core/models.py")

# Get document symbols (classes, functions, etc.)
symbols = basedpyright.document_symbols("core/models.py")
```

- All line/column parameters are **0-indexed**
- Returns `None` when not found (consistent with codebase patterns)
- Uses `--stdio` transport via `lsp` package (sans-IO LSP implementation)
- Thread-safe singleton — one langserver process reused across all requests

### Database Notes

- Materialized views: `mv_monthly_category_totals`, `mv_daily_tx_counts`
- Startup jobs (`run_startup_jobs`): cleanup_sessions → process_recurring → reconcile_balances → refresh_views → take_snapshots

## Git Workflow

See `.gemini/rules/git-workflow.md` for:

- Commit practices (never commit without asking, never use `git add .`)
- Workflow (show changes → ask → wait for approval → commit)
- Commit message format (conventional commits)
- Handling unrelated changes
