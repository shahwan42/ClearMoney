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

```text
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

```text
HTTP Request → Middleware → Handler → Service → Repository → PostgreSQL
```

- **Handlers** parse HTTP, call services, render templates or JSON
- **Services** contain business logic, call repositories
- **Repositories** execute SQL queries, return models
- **Models** are plain structs with `json` and `db` tags — no ORM

### Key Design Patterns

| Pattern | Details |
| ------- | ------- |
| Template rendering | Clone-per-page: base layout + components cloned, page parsed on top |
| Monetary values | `NUMERIC(15,2)` in DB, `float64` in Go |
| Nullable fields | Pointer types (`*string`, `*float64`) = SQL NULL |
| Auth | PIN-based with bcrypt, HMAC session tokens, cookie-based sessions |
| Balance tracking | Atomic updates via DB transactions, `balance_delta` per transaction for reconciliation |
| Logging | `log/slog` structured logging, request-scoped via middleware (`authmw.Log(ctx)`) |
| Charts | CSS-only (conic-gradient donuts, flexbox bars, inline SVG sparklines) — no Chart.js |
| Frontend | HTMX for dynamic updates, Tailwind CSS via CDN, dark mode (class-based) |
| Redirects | `htmxRedirect(w, r, url)` — detects HX-Request header, sends HX-Redirect or http.Redirect |
| HTMX results | `renderHTMXResult(w, type, msg, detail)` — consistent success/error/info partials |
| Date inputs | Server-side `value="{{formatDateISO .Today}}"` — view model structs carry `.Today` field |

### Service Wiring

`NewPageHandler` takes 15 constructor params + 4 setter-injected services:

- `SetSnapshotService`, `SetVirtualFundService`, `SetBudgetService`, `SetAccountHealthService`

`DashboardService` aggregates from 10+ sources via setter pattern:

- `SetExchangeRateRepo`, `SetPersonRepo`, `SetInvestmentRepo`, `SetStreakService`, etc.

## Database

- **Driver**: pgx v5 (via `database/sql` stdlib interface)
- **Migrations**: `golang-migrate` with embedded SQL files (`internal/database/migrations/`)
- **20 migrations** (000000–000019): init → institutions → accounts → categories → persons → transactions → exchange_rates → seed_categories → user_config → recurring_rules → investments → installments → balance_delta → indexes/views → snapshots → virtual_funds → budgets → account_health → remove_checking_account_type → category_icons_and_unique
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

### Commit Message Convention

Use conventional commits: `type: concise description`

- `feat:` new feature — `fix:` bug fix — `refactor:` code restructure — `docs:` documentation
- `chore:` tooling/config — `test:` test additions — keep message under ~72 chars

### Adding a New Feature

1. **Migration**: `make migrate-create name=create_foo` → edit the `.up.sql` and `.down.sql`
2. **Model**: Add struct to `internal/models/foo.go`
3. **Repository**: Add `internal/repository/foo.go` with SQL queries
4. **Service**: Add `internal/service/foo.go` with business logic
5. **Handler**: Add routes in `internal/handler/router.go`, handler methods in appropriate file
6. **Template**: Add `internal/templates/pages/foo.html` and any partials
7. **Tests**: Write integration tests using `testutil.NewTestDB(t)`

### Feature Delivery Checklist

After implementing a feature, always follow these steps before considering it done:

1. **Run feature tests** — run the relevant unit and integration tests for the new feature; confirm they pass
2. **Run full test suite** — run `make test && make test-integration` to confirm no regressions
3. **Restart the app** — kill any existing server (`lsof -ti:8080 | xargs kill`), then run `make run` so the user can try the feature live at `http://0.0.0.0:8080`. Templates are embedded at compile time, so a restart is required even for template-only changes.
4. **Show manual test steps** — list the exact UI steps the user should follow to try the feature
5. **Wait for approval** — do not proceed until the user confirms the feature works as expected
6. **Ask to commit** — once approved, ask the user if they'd like to commit the change

### Wiring a New Service into PageHandler

When adding a new service that PageHandler needs:

1. Add a field to `PageHandler` struct in `pages.go` (~line 295)
2. Add a `SetFooService(svc *service.FooService)` setter method
3. In `router.go`, instantiate the repo + service, then call `pages.SetFooService(fooSvc)`
4. If dashboard needs it too: add a setter on `DashboardService` and call `dashboardSvc.SetFooService(fooSvc)`

**Why setters?** Avoids growing the already-15-param constructor. Setter-injected services are nil-safe.

### HTMX Response Patterns

Choose the right response type based on the action:

| Scenario | Pattern | Example |
| -------- | ------- | ------- |
| After form submit, go to new page | `htmxRedirect(w, r, "/target")` | Create transaction → redirect to list |
| Show success/error inline | `h.renderHTMXResult(w, "success", "Saved!", "")` | Budget created |
| Return HTML fragment for swap | `tmpl.ExecuteTemplate(w, "partial-name", data)` | Load more transactions |
| Update another part of page (OOB) | Write `<div id="target" hx-swap-oob="true">...</div>` | Refresh account list after adding account |
| Standard POST (non-HTMX form) | `http.Redirect(w, r, url, http.StatusSeeOther)` | Logout form |

**Key pitfall**: If a form uses standard `<form method="POST">` (no `hx-post`), use `http.Redirect`, NOT `htmxRedirect`. Using HTMX redirect on a standard POST causes the response HTML to nest inside the page.

### Template Patterns

- **Pages**: `internal/templates/pages/foo.html` — must define `{{define "title"}}` and `{{define "content"}}` blocks
- **Partials**: `internal/templates/partials/foo.html` — define `{{define "foo"}}...{{end}}`, auto-discovered
- **View models**: Define a struct in `pages.go` near line 125 (e.g., `FooPageData`) — becomes the `.Data` field in `PageData`
- **Bare pages** (no header/nav): Add page name to `barePages` map in `templates.go` (currently: login, setup)
- **Template functions**: Add to `TemplateFuncs()` in `templates.go` — available in all templates as `{{funcName .Arg}}`
- **Pass multiple values to partials**: Use `{{template "partial" (dict "Key1" .Val1 "Key2" .Val2)}}`

### Page Handler Method Structure

Standard form-handling handler method pattern in `pages.go`:

```go
func (h *PageHandler) FooCreate(w http.ResponseWriter, r *http.Request) {
    // 1. Parse form
    if err := r.ParseForm(); err != nil { ... }

    // 2. Build model from form values
    foo := models.Foo{Name: r.FormValue("name")}

    // 3. Parse optional/numeric fields safely
    if v := r.FormValue("amount"); v != "" {
        if f, err := parseFloat(v); err == nil { foo.Amount = f }
    }

    // 4. Call service
    if _, err := h.fooSvc.Create(r.Context(), foo); err != nil {
        authmw.Log(r.Context()).Warn("foo create failed", "error", err)
        // Return error HTML or renderHTMXResult
        return
    }

    // 5. Success response — redirect or render result partial
    htmxRedirect(w, r, "/foo")
}
```

### Common Pitfalls (from QA)

- **Float comparison in templates**: Use `{{if gt .Amount 0.0}}` not `{{if gt .Amount 0}}` — Go templates can't compare `float64` with untyped `int`
- **Date inputs**: Always pre-populate with `value="{{formatDateISO .Today}}"` — add a `Today time.Time` field to view model structs
- **HTMX nesting bug**: Forms that use standard `<form method="POST" action="/path">` must NOT use `htmxRedirect` — use `http.Redirect(w, r, url, http.StatusSeeOther)` instead
- **Credit card balance signs**: CC balances are stored as negative numbers (representing debt). Display with `neg` template func when showing "amount used"
- **Category dropdowns**: Use `<optgroup label="Expenses">` and `<optgroup label="Income">` — pass both `ExpenseCategories` and `IncomeCategories` to templates
- **Enum casting in SQL**: When filtering by enum columns (e.g., `currency`), cast the Go string: `WHERE currency = $1::currency_type`
- **OOB swaps**: When an HTMX response needs to update multiple page sections, write the primary response first, then OOB divs with `hx-swap-oob="true"`

### Startup Sequence

`main.go` runs: migrations → process recurring rules → reconcile balances → refresh materialized views → take snapshots → start HTTP server

## Environment Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
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
