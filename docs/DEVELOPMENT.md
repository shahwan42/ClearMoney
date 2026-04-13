# Development Guide — Local Environment Setup

This guide covers everything needed to set up a complete local development environment for ClearMoney, including the AI agentic workflow tools (MCP servers).

For deployment, see [DEPLOYMENT.md](./DEPLOYMENT.md).

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | >= 3.12 | Backend runtime |
| **uv** | latest | Python package manager (workspace) |
| **Node.js** | >= 20 | MCP servers (npx pulls packages) |
| **npm** | latest | Comes with Node.js |
| **PostgreSQL** | 16 | Database |
| **Chrome** | stable | Browser for `chrome-devtools-mcp` |
| **Git** | any | Version control |
| **Docker** | any | Optional — PostgreSQL container |

### Verify Installs

```bash
python --version   # >= 3.12
uv --version      # any recent version
node --version    # >= 20
npm --version
psql --version    # postgres: 16
docker --version
```

---

## 1. Clone & Environment

```bash
git clone https://github.com/shahwan42/clearmoney.git
cd clearmoney

cp .env.example .env
```

Edit `.env`:

```bash
# Database — two options:
#   Option A (Docker):    postgres://clearmoney:clearmoney@localhost:5433/clearmoney
#   Option B (bare metal): postgres://clearmoney:clearmoney@localhost:5432/clearmoney
DATABASE_URL=postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable

ENV=development
LOG_LEVEL=debug

# Magic link auth — leave empty for dev mode (emails logged to console)
RESEND_API_KEY=
APP_URL=http://localhost:8000
```

---

## 2. Python Dependencies

ClearMoney uses a **unified uv workspace** for backend and e2e dependencies.

```bash
uv sync
```

This installs:
- `backend/` — Django, pytest, ruff, mypy, django-ai-boost, etc.
- `e2e/` — pytest, pytest-playwright, psycopg, etc.

### Python Version Check

```bash
python --version  # must be >= 3.12
```

If you need a newer Python, use `uv python install 3.12` or your preferred version manager (pyenv, mise, etc.).

---

## 3. Database Setup

### Option A: Docker (Recommended)

```bash
docker compose up -d db
```

Waits for PostgreSQL to be healthy, then done.

### Option B: Bare Metal PostgreSQL

On macOS with Colima (SSH tunnel), ensure PostgreSQL 16 is running on port 5433. The `DATABASE_URL` in `.env` should use `localhost:5433`.

### Run Migrations

```bash
# Fresh database
make migrate

# Existing database with pre-existing tables (mark as migrated without running SQL)
make fake-initial
```

---

## 4. Git Hooks

```bash
make setup-hooks
```

Installs the pre-commit hook that lints code before each commit.

---

## 5. MCP Server Setup

ClearMoney includes 4 MCP servers for AI agentic workflows. The configuration lives in `.mcp.json` and is automatically loaded by opencode.

### Prerequisites

**Node.js** is required — `npx` pulls the MCP packages at runtime. If Node.js is not installed, MCP servers will fail to start.

**Playwright browsers** must be installed:

```bash
npx playwright install
```

This downloads:
- Chromium (Chrome for Testing)
- Firefox
- WebKit

### MCP Servers

| Server | Package | Purpose |
|--------|---------|---------|
| **django-ai-boost** | `django-ai-boost` (Python) | Django introspection — list models, migrations, URLs, run system checks |
| **context7** | `@upstash/context7-mcp` | Up-to-date library docs for any prompt — no API key needed (rate-limited) |
| **playwright** | `@playwright/mcp` | Browser automation for visual QA — accessibility snapshots, screenshots, keyboard nav |
| **chrome-devtools** | `chrome-devtools-mcp` | Chrome DevTools for performance analysis, network inspection, debugging |

### Usage Examples

```bash
# Django system check (fast)
mcp__django-ai-boost__run_check

# List all URL routes
mcp__django-ai-boost__list_urls

# List Django models
mcp__django-ai-boost__list_models

# Browser accessibility snapshot
mcp__playwright__browser_snapshot

# Navigate browser
mcp__playwright__browser_navigate{"url": "http://localhost:8000"}

# Get library docs
mcp__context7__resolve_library_id{"libraryName": "django"}

# Performance trace
mcp__chrome-devtools__performance_start_trace
```

### Optional: Context7 API Key

Context7 works without an API key (rate-limited). For higher limits, get a free key at [context7.com/dashboard](https://context7.com/dashboard) and add to `.env`:

```bash
CONTEXT7_API_KEY=your_key_here
```

### Restart opencode

After any changes to `.mcp.json`, restart opencode to reload MCP servers.

---

## 6. Running the App

```bash
make run
```

Opens Django dev server at `http://localhost:8000`.

First visit: enter your email → magic link sent (logged to console in dev mode).

---

## 7. Running Tests

```bash
# Unit + integration tests (requires running DB)
make test

# Parallel tests (faster)
make test-fast

# E2E browser tests (requires running app)
make test-e2e

# Linting (ruff + mypy + import-linter)
make lint

# Auto-format code
make format

# Coverage report
make coverage
```

---

## 8. Common Development Tasks

```bash
make migrate              # Apply pending migrations
make makemigrations       # Generate new migrations
make reconcile            # Check balance consistency
make reconcile-fix        # Auto-fix balance discrepancies
make seed                 # Populate sample data
make shell                # Django shell
make logs                 # Stream Docker logs
make startup-jobs         # Run all startup background jobs
```

---

## 9. Troubleshooting

| Issue | Solution |
|-------|----------|
| DB connection error | Check `DATABASE_URL` — Docker uses port 5433 on host, bare metal uses 5432 |
| MCP servers not loaded | Restart opencode after editing `.mcp.json` |
| `playwright` MCP tool fails | Run `npx playwright install` to install browsers |
| Migration error | Ensure DB is running (`docker compose up -d db`) and `DATABASE_URL` is correct |
| `uv sync` fails | Ensure Python >= 3.12 is active: `python --version` |
| Magic link not received | Check console output — in dev mode emails are logged, not sent |
| Port 8000 in use | Stop other services or change port in `Makefile` (`run` target) |

---

## Quick Reference

```bash
# Full setup
git clone <repo>
cd clearmoney
cp .env.example .env
# edit .env DATABASE_URL
uv sync
docker compose up -d db
make migrate
make setup-hooks
npx playwright install

# Start dev server
make run
```
