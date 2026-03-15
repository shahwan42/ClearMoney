# ClearMoney — AI Assistant Instructions

> Personal finance tracker built with Go, HTMX, Tailwind CSS, and PostgreSQL.
> Single-user PWA for tracking accounts, transactions, budgets, and investments across Egyptian banks.

## ⚠️ Production App — No Breaking Changes

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
- **Background**: PHP Laravel, Python Django — learning Go, HTMX, PostgreSQL
- **Preferences**: Use Laravel/Django analogies when explaining Go concepts. Keep comments descriptive but not verbose. Follow DRY principles.

## Quick Start

```bash
docker compose up -d          # Start PostgreSQL (port 5433)
make run                      # Start dev server on :8080
make test                     # Unit tests
make test-integration         # Integration tests (needs running DB)
make lint                     # Run golangci-lint
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
  timeutil/               # Timezone utilities: Now(), Today(), MonthStart/End, ParseDateInTZ
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
| Logging | 3-layer structured logging: StructuredLogger middleware → service events (`logutil.LogEvent`) → page views (`authmw.Log(ctx)`) |
| Charts | CSS-only (conic-gradient donuts, flexbox bars, inline SVG sparklines) — no Chart.js |
| Frontend | HTMX for dynamic updates, Tailwind CSS via CDN, dark mode (class-based) |
| Redirects | `htmxRedirect(w, r, url)` — detects HX-Request header, sends HX-Redirect or http.Redirect |
| HTMX results | `renderHTMXResult(w, type, msg, detail)` — consistent success/error/info partials |
| Date inputs | Server-side `value="{{formatDateISO .Today}}"` — view model structs carry `.Today` field |

### Service Wiring

`NewPageHandler` takes 15 constructor params + 4 setter-injected services:

- `SetSnapshotService`, `SetVirtualAccountService`, `SetBudgetService`, `SetAccountHealthService`

`DashboardService` aggregates from 10+ sources via setter pattern:

- `SetExchangeRateRepo`, `SetPersonRepo`, `SetInvestmentRepo`, `SetStreakService`, etc.

## Database

- **Driver**: pgx v5 (via `database/sql` stdlib interface)
- **Migrations**: `golang-migrate` with embedded SQL files (`internal/database/migrations/`)
- **22 migrations** (000000–000022): init → institutions → accounts → categories → persons → transactions → exchange_rates → seed_categories → user_config → recurring_rules → investments → installments → balance_delta → indexes/views → snapshots → virtual_funds → budgets → account_health → remove_checking_account_type → category_icons_and_unique → cash_and_wallet → rename_virtual_funds_to_virtual_accounts
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
- Timezone handling: Always use `timeutil.Now()` instead of `time.Now()` for business logic. Use `timeutil.Today(loc)` for calendar-date operations (e.g., "today", streak, snapshots). Use `timeutil.MonthStart/MonthEnd` for month boundaries. Leave `time.Now()` for performance timing and infrastructure (auth, middleware). Services that need timezone get a `SetTimezone(loc *time.Location)` setter

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

### Logging Conventions

ClearMoney uses a 3-layer structured logging architecture:

1. **Request middleware** (`StructuredLogger` in `internal/middleware/logging.go`): Logs every request with status, duration, bytes, route pattern, HTMX detection, and device type. Skips `/static/*` and `/healthz`.

2. **Service events** (`logutil.LogEvent` in `internal/logutil/logutil.go`): Every mutating service method must call `logutil.LogEvent(ctx, "entity.action", ...)` after successful completion. Event names use `entity.action` format (e.g., `transaction.created`, `budget.deleted`). Log IDs, types, currencies — never amounts, PINs, or PII.

3. **Page views** (`authmw.Log(r.Context()).Info("page viewed", "page", "<name>")` in handlers): Every page handler logs which page is being viewed. HTMX partial handlers log `"partial loaded"`.

**Import patterns:**
- Handlers: `authmw "github.com/shahwan42/clearmoney/internal/middleware"` → `authmw.Log(r.Context())`
- Services: `"github.com/shahwan42/clearmoney/internal/logutil"` → `logutil.LogEvent(ctx, ...)`
- Debug logging: `logutil.Log(ctx).Debug(...)` in services, `slog.Debug(...)` in handlers

**Log levels:** Info for events/pages, Debug for dev tracing (enabled with `LOG_LEVEL=debug`), Warn/Error for failures.

### Adding a New Feature

1. **Migration**: `make migrate-create name=create_foo` → edit the `.up.sql` and `.down.sql`
2. **Model**: Add struct to `internal/models/foo.go`
3. **Repository**: Add `internal/repository/foo.go` with SQL queries
4. **Service**: Add `internal/service/foo.go` with business logic
5. **Logging**: Add `logutil.LogEvent(ctx, "foo.created", ...)` for mutations in service, `authmw.Log(r.Context()).Info("page viewed", "page", "foo")` for page handlers
6. **Handler**: Add routes in `internal/handler/router.go`, handler methods in appropriate file
7. **Template**: Add `internal/templates/pages/foo.html` and any partials
8. **Unit tests**: Test service logic and helpers in isolation (e.g., `internal/service/foo_test.go`) — no DB required
9. **Integration tests**: Test repository and handler layers against a real DB using `testutil.NewTestDB(t)` (e.g., `internal/repository/foo_test.go`, `internal/handler/foo_test.go`)
10. **E2e tests**: Write Playwright browser tests that exercise the full user flow (e.g., `e2e/foo.spec.ts`) — navigates pages, fills forms, asserts visible results
11. **Documentation**: Add or update feature doc in `docs/features/foo.md` — describe what it does, key files, architecture, and tips for newcomers. Update `docs/FEATURES.md` if adding a new feature.

### Feature Delivery Checklist

After implementing a feature, always follow these steps before considering it done:

1. **Run unit tests** — run `make test` to confirm all unit tests pass (no DB required)
2. **Run integration tests** — run `make test-integration` to confirm all integration tests pass (requires running DB)
3. **Run e2e tests** — run `make test-e2e` to confirm all end-to-end tests pass (Playwright browser tests against a running app)
4. **Run linter** — run `make lint` to confirm no lint errors (requires golangci-lint installed)
5. **Update documentation** — add or update the relevant feature doc in `docs/features/`. Update `docs/FEATURES.md` if the feature is new.
6. **Verify logging** — check that service events and page views are logged at Info level when exercising the feature
7. **Restart the app** — kill any existing server (`lsof -ti:8080 | xargs kill`), then run `make run` so the user can try the feature live at `http://0.0.0.0:8080`. Templates are embedded at compile time, so a restart is required even for template-only changes.
8. **Show manual test steps** — list the exact UI steps the user should follow to try the feature
9. **Wait for approval** — do not proceed until the user confirms the feature works as expected
10. **Ask to commit** — once approved, ask the user if they'd like to commit the change

All three test levels, the linter, and documentation must pass/be updated before restarting the app for manual testing.

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
| Destructive action with confirmation | Bottom sheet + `hx-delete` with name-match input | Delete account |

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
- **Transaction currency**: Never trust the form's currency field — the service layer overrides it from the account. Don't add client-side currency logic; the server is the source of truth

### Startup Sequence

`main.go` runs: migrations → process recurring rules → reconcile balances → refresh materialized views → take snapshots → start HTTP server

## Environment Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `PORT` | `8080` | HTTP server port |
| `DATABASE_URL` | (none) | PostgreSQL connection string |
| `ENV` | `development` | Environment mode |
| `LOG_LEVEL` | `info` | Logging level: debug, info, warn, error |
| `APP_TIMEZONE` | `Africa/Cairo` | User timezone for date display and calendar logic |
| `VAPID_PUBLIC_KEY` | (none) | Web Push VAPID public key |
| `VAPID_PRIVATE_KEY` | (none) | Web Push VAPID private key |

## Dependencies (go.mod)

- `github.com/go-chi/chi/v5` — HTTP router
- `github.com/golang-migrate/migrate/v4` — Database migrations
- `github.com/jackc/pgx/v5` — PostgreSQL driver
- `golang.org/x/crypto` — bcrypt for PIN hashing
- `log/slog` — Structured logging (stdlib, no external dep)
