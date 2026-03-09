# ClearMoney — AI Assistant Instructions

> Personal finance tracker built with Go, HTMX, Tailwind CSS, and PostgreSQL.
> Single-user PWA for tracking accounts, transactions, budgets, and investments across Egyptian banks.

## Developer Profile

- **Name**: Ahmed
- **Background**: PHP Laravel, Python Django — learning Go, HTMX, PostgreSQL
- **Preferences**: Use Laravel/Django analogies when explaining Go concepts. Keep comments descriptive but not verbose. Follow DRY principles.

## Quick Start

```bash
docker compose up -d          # Start PostgreSQL (port 5433)
make run                      # Start dev server on :8080
make test                     # Unit tests
make test-integration         # Integration tests (needs running DB)
make seed                     # Populate sample data
make reconcile                # Check balance consistency
```

## Architecture

```
cmd/
  server/main.go          # Entry point — config → DB → migrations → router → HTTP server
  reconcile/main.go       # CLI tool for balance verification
  seed/main.go            # Seed data command
internal/
  config/                 # Environment-based config (like Laravel's config/)
  database/               # Connection, migrations (golang-migrate, embedded SQL)
  handler/                # HTTP handlers + routes (like Laravel Controllers + routes/web.php)
  jobs/                   # Background tasks: reconcile, snapshots, refresh views
  middleware/              # Auth (PIN-based) + request logging (slog)
  models/                 # Domain structs (like Eloquent models, no ORM)
  repository/             # Database queries (like Laravel Repositories)
  service/                # Business logic (like Laravel Services)
  templates/              # Embedded HTML templates (Go html/template)
  testutil/               # Test DB helpers + fixture factories
static/                   # CSS, JS, service worker, manifest
```

### Layered Architecture

```
HTTP Request → Middleware → Handler → Service → Repository → PostgreSQL
```

- **Handlers** parse HTTP, call services, render templates or JSON
- **Services** contain business logic, call repositories
- **Repositories** execute SQL queries, return models
- **Models** are plain structs with `json` and `db` tags — no ORM

### Key Design Patterns

| Pattern | Details |
|---------|---------|
| Template rendering | Clone-per-page: base layout + components cloned, page parsed on top |
| Monetary values | `NUMERIC(15,2)` in DB, `float64` in Go |
| Nullable fields | Pointer types (`*string`, `*float64`) = SQL NULL |
| Auth | PIN-based with bcrypt, HMAC session tokens, cookie-based sessions |
| Balance tracking | Atomic updates via DB transactions, `balance_delta` per transaction for reconciliation |
| Logging | `log/slog` structured logging, request-scoped via middleware (`authmw.Log(ctx)`) |
| Charts | CSS-only (conic-gradient donuts, flexbox bars, inline SVG sparklines) — no Chart.js |
| Frontend | HTMX for dynamic updates, Tailwind CSS via CDN, dark mode (class-based) |

### Service Wiring

`NewPageHandler` takes 15 constructor params + 4 setter-injected services:
- `SetSnapshotService`, `SetVirtualFundService`, `SetBudgetService`, `SetAccountHealthService`

`DashboardService` aggregates from 10+ sources via setter pattern:
- `SetExchangeRateRepo`, `SetPersonRepo`, `SetInvestmentRepo`, `SetStreakService`, etc.

## Database

- **Driver**: pgx v5 (via `database/sql` stdlib interface)
- **Migrations**: `golang-migrate` with embedded SQL files (`internal/database/migrations/`)
- **17 migrations**: institutions → accounts → categories → persons → transactions → exchange rates → user_config → recurring_rules → investments → installments → balance_delta → indexes/views → snapshots → virtual_funds → budgets → account_health
- **Materialized views**: `mv_monthly_category_totals`, `mv_daily_tx_counts`
- **Connection**: `DATABASE_URL` env var, port `5433` (Colima, not 5432)

## Testing

- **TDD workflow**: RED test → GREEN implementation → refactor
- **Integration tests**: Real PostgreSQL (not mocks), run with `-p 1` for serial execution
- **Test DB**: `TEST_DATABASE_URL=postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable`
- **Fixture factories**: `testutil.CreateInstitution(t, db, models.Institution{...})`
- **Auth helper**: `testutil.SetupAuth(t, db)` returns a session cookie for authenticated requests
- **Clean tables**: `testutil.CleanTable(t, db, "transactions")`

## Coding Conventions

### Go Style
- Package comments include Laravel/Django analogies for learning
- Template float comparison: use `0.0` not `0` (Go templates can't compare float64 with int)
- Error wrapping: `fmt.Errorf("operation: %w", err)` at service/repo layers
- Structured logging: `slog.Error("msg", "key", value)` — never log PINs or secrets

### respondError Pattern
All JSON API errors go through `respondError(w, r, status, message)` which auto-logs:
- `5xx` → `slog.Error` with request_id, method, path
- `4xx` → `slog.Warn` with request_id, method, path

### Page Handler Errors
For HTML page handlers, add `authmw.Log(r.Context()).Error(...)` before `http.Error()` on 500s.

### Adding a New Feature
1. **Migration**: `make migrate-create name=create_foo` → edit the `.up.sql` and `.down.sql`
2. **Model**: Add struct to `internal/models/foo.go`
3. **Repository**: Add `internal/repository/foo.go` with SQL queries
4. **Service**: Add `internal/service/foo.go` with business logic
5. **Handler**: Add routes in `internal/handler/router.go`, handler methods in appropriate file
6. **Template**: Add `internal/templates/pages/foo.html` and any partials
7. **Tests**: Write integration tests using `testutil.NewTestDB(t)`

### Startup Sequence
`main.go` runs: migrations → process recurring rules → reconcile balances → refresh materialized views → take snapshots → start HTTP server

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | HTTP server port |
| `DATABASE_URL` | (none) | PostgreSQL connection string |
| `ENV` | `development` | Environment mode |
| `LOG_LEVEL` | `info` | Logging level: debug, info, warn, error |
| `VAPID_PUBLIC_KEY` | (none) | Web Push VAPID public key |
| `VAPID_PRIVATE_KEY` | (none) | Web Push VAPID private key |

## Dependencies (go.mod)

- `github.com/go-chi/chi/v5` — HTTP router
- `github.com/golang-migrate/migrate/v4` — Database migrations
- `github.com/jackc/pgx/v5` — PostgreSQL driver
- `golang.org/x/crypto` — bcrypt for PIN hashing
- `log/slog` — Structured logging (stdlib, no external dep)
