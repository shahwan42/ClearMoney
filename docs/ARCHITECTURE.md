# ClearMoney Architecture Guide

> Written for developers coming from **Laravel (PHP)** or **Django (Python)**.
> Every concept is mapped to its equivalent in those frameworks.

---

## 1. The Big Picture

ClearMoney is a **server-rendered** personal finance app built with:

| Concern        | Go Stack                    | Laravel Equivalent          | Django Equivalent            |
|----------------|-----------------------------|-----------------------------|------------------------------|
| HTTP Router    | chi v5                     | `routes/web.php`            | `urls.py`                    |
| Controllers    | `handler/*.go`              | `app/Http/Controllers/`     | `views.py`                   |
| Business Logic | `service/*.go`              | `app/Services/`             | `services.py` (custom)       |
| Database Layer | `repository/*.go`           | Eloquent Models (queries)   | Django ORM QuerySets         |
| Data Structs   | `models/*.go`               | Eloquent Models (schema)    | `models.py` (fields)         |
| Templates      | Go `html/template`          | Blade templates             | Django Templates (Jinja2)    |
| Migrations     | golang-migrate (raw SQL)    | `php artisan migrate`       | `python manage.py migrate`   |
| Middleware     | `middleware/auth.go`        | `app/Http/Middleware/`      | Django middleware classes     |
| Config         | Environment variables       | `.env` + `config/*.php`     | `settings.py`                |
| Background Jobs| `jobs/*.go`                 | Laravel Queues / Commands   | Celery tasks / management cmds |
| Tests          | Go `testing` package        | PHPUnit                     | pytest / unittest            |

### Request Flow (how a request travels through the code)

```
Browser Request
     |
     v
cmd/server/main.go          -- Entry point (like index.php or manage.py runserver)
     |
     v
handler/router.go           -- URL routing (like routes/web.php or urls.py)
     |
     v
middleware/auth.go           -- Auth check (like Laravel auth middleware)
     |
     v
handler/pages.go             -- Page handler (like a Controller method)
handler/account.go           -- or API handler (JSON responses)
     |
     v
service/transaction.go       -- Business logic (like a Service class)
     |
     v
repository/transaction.go    -- SQL queries (like Eloquent or Django ORM)
     |
     v
PostgreSQL                   -- Database
     |
     v
templates/pages/home.html    -- HTML rendering (like Blade or Django templates)
     |
     v
Browser Response
```

---

## 2. Directory Structure

```
clear-money_claude-only/
|
+-- cmd/                          # Executable entry points
|   +-- server/main.go            # The web server (like `php artisan serve`)
|   +-- reconcile/main.go         # CLI for balance checking (like `php artisan command`)
|   +-- seed/main.go              # CLI for seeding dev data (like `php artisan db:seed`)
|
+-- internal/                     # Private app code (Go convention: can't be imported by others)
|   |
|   +-- config/                   # Environment config (like config/*.php or settings.py)
|   |   +-- config.go             #   Reads DATABASE_URL, PORT, ENV from environment
|   |
|   +-- database/                 # Database connection + migrations
|   |   +-- database.go           #   Connection pool setup (like config/database.php)
|   |   +-- migrate.go            #   Migration runner (like `artisan migrate` internals)
|   |   +-- migrations/           #   Raw SQL migration files (like database/migrations/)
|   |   |   +-- 000000_init.up.sql
|   |   |   +-- 000001_create_institutions.up.sql
|   |   |   +-- ...
|   |   +-- seeds/                #   Sample data for development
|   |       +-- seed.go           #     (like database/seeders/DatabaseSeeder.php)
|   |
|   +-- models/                   # Domain structs (like Eloquent Model definitions)
|   |   +-- institution.go        #   Institution struct + InstitutionType enum
|   |   +-- account.go            #   Account struct + AccountType/Currency enums
|   |   +-- transaction.go        #   Transaction struct + TransactionType enum
|   |   +-- category.go           #   Category struct
|   |   +-- person.go             #   Person struct (for loans/debts)
|   |   +-- recurring.go          #   RecurringRule struct
|   |   +-- investment.go         #   Investment struct
|   |   +-- installment.go        #   InstallmentPlan struct
|   |   +-- exchange_rate.go      #   ExchangeRateLog struct
|   |   +-- snapshot.go           #   DailySnapshot + AccountSnapshot structs
|   |   +-- virtual_account.go   #   VirtualAccount struct
|   |   +-- budget.go            #   Budget struct
|   |   +-- chart.go             #   ChartSegment struct (shared between service + handler)
|   |
|   +-- repository/               # Database queries (like Eloquent query scopes)
|   |   +-- institution.go        #   INSERT, SELECT, UPDATE, DELETE for institutions
|   |   +-- account.go            #   Same for accounts
|   |   +-- transaction.go        #   Same for transactions (most complex)
|   |   +-- category.go           #   Same for categories
|   |   +-- person.go             #   Same for persons
|   |   +-- recurring.go          #   Same for recurring rules
|   |   +-- investment.go         #   Same for investments
|   |   +-- installment.go        #   Same for installment plans
|   |   +-- exchange_rate.go      #   Same for exchange rate log
|   |   +-- snapshot.go          #   Same for snapshots (daily + account)
|   |   +-- virtual_account.go   #   Same for virtual accounts
|   |   +-- budget.go            #   Same for budgets
|   |
|   +-- service/                  # Business logic layer (like app/Services/)
|   |   +-- transaction.go        #   Core: create tx + update balance atomically
|   |   +-- account.go            #   Account CRUD + billing cycle logic
|   |   +-- institution.go        #   Institution CRUD
|   |   +-- category.go           #   Category CRUD with system-category protection
|   |   +-- dashboard.go          #   Aggregates data for the home page
|   |   +-- person.go             #   Loan/repayment with double-entry accounting
|   |   +-- auth.go               #   PIN hashing, session management
|   |   +-- salary.go             #   Multi-step salary distribution wizard
|   |   +-- reports.go            #   Monthly spending reports
|   |   +-- recurring.go          #   Recurring rule processing
|   |   +-- investment.go         #   Investment portfolio CRUD
|   |   +-- installment.go        #   Installment plan CRUD
|   |   +-- export.go             #   CSV export
|   |   +-- streak.go             #   Daily logging streak
|   |   +-- notifications.go      #   Push notification conditions
|   |   +-- snapshot.go          #   Daily balance snapshot capture + backfill
|   |   +-- virtual_account.go   #   Virtual account CRUD + allocation
|   |   +-- budget.go            #   Budget CRUD + threshold checks
|   |   +-- account_health.go    #   Min-balance and min-deposit health rules
|   |
|   +-- handler/                  # HTTP handlers (like Controllers)
|   |   +-- router.go             #   All route definitions (like routes/web.php)
|   |   +-- pages.go              #   HTML page handlers (the big one - 1900+ lines)
|   |   +-- auth.go               #   Login/setup/logout pages
|   |   +-- account.go            #   REST API for accounts (JSON)
|   |   +-- institution.go        #   REST API for institutions (JSON)
|   |   +-- category.go           #   REST API for categories (JSON)
|   |   +-- transaction.go        #   REST API for transactions (JSON)
|   |   +-- person.go             #   REST API for people (JSON)
|   |   +-- push.go               #   Push notification endpoints
|   |   +-- templates.go          #   Template engine setup + helper functions
|   |   +-- response.go           #   JSON response helpers
|   |   +-- charts.go             #   Chart template functions + data types (donut, bar, sparkline, trend)
|   |   +-- health.go             #   GET /healthz endpoint + account health handlers
|   |
|   +-- middleware/               # HTTP middleware
|   |   +-- auth.go               #   Session cookie validation (like auth:web middleware)
|   |   +-- logging.go            #   Request logging with slog (request_id, method, path)
|   |
|   +-- jobs/                     # Background/CLI jobs
|   |   +-- reconcile.go          #   Balance reconciliation checker
|   |   +-- refresh_views.go      #   Refresh materialized views
|   |   +-- snapshot.go           #   Daily balance snapshots + backfill
|   |
|   +-- templates/                # HTML templates (like resources/views/)
|   |   +-- embed.go              #   Embeds templates into the binary
|   |   +-- layouts/              #   Base layouts (like layouts/app.blade.php)
|   |   |   +-- base.html         #     Full page with header + nav + HTMX/Tailwind
|   |   |   +-- bare.html         #     Minimal layout for login/setup pages
|   |   +-- components/           #   Reusable UI components
|   |   |   +-- header.html       #     Top header bar
|   |   |   +-- bottom-nav.html   #     Bottom nav with FAB + quick entry sheet
|   |   +-- pages/                #   Full page templates (like resources/views/pages/)
|   |   |   +-- home.html         #     Dashboard
|   |   |   +-- accounts.html     #     Accounts management
|   |   |   +-- transactions.html #     Transaction list with filters
|   |   |   +-- ...
|   |   +-- partials/             #   HTMX swappable fragments (like Blade components)
|   |       +-- transaction-row.html
|   |       +-- institution-card.html
|   |       +-- ...
|   |
|   +-- testutil/                 # Test helpers
|       +-- testdb.go             #   Test DB connection + cleanup
|       +-- fixtures.go           #   Factory functions (like Laravel model factories)
|
+-- static/                       # Static assets served at /static/
|   +-- css/app.css               #   Custom CSS
|   +-- js/                       #   JavaScript files
|   +-- icons/                    #   PWA icons
|   +-- manifest.json             #   PWA manifest
|
+-- e2e/                          # End-to-end tests (Playwright)
|   +-- tests/*.spec.ts           #   Browser-based tests
|
+-- Makefile                      # Build/run shortcuts (like composer scripts)
+-- Dockerfile                    # Container build
+-- docker-compose.yml            # Local dev environment
+-- go.mod                        # Go dependencies (like composer.json)
+-- go.sum                        # Lock file (like composer.lock)
```

---

## 3. Key Go Concepts for Laravel/Django Developers

### 3.1 Packages = Namespaces

In Go, each directory is a **package**. A file's first line declares its package:
```go
package models  // This file is part of the "models" package
```

This is like PHP namespaces (`namespace App\Models;`) or Python modules (`from app.models import ...`).

### 3.2 Structs = Classes (sort of)

Go has no classes. Instead, **structs** hold data and **methods** attach behavior:

```go
// Laravel: class Account extends Model { ... }
// Django:  class Account(models.Model): ...
// Go:
type Account struct {
    ID   string  `json:"id"`
    Name string  `json:"name"`
}

// Method on Account (like a class method)
func (a Account) IsCreditType() bool {
    return a.Type == AccountTypeCreditCard
}
```

### 3.3 Interfaces = Duck Typing

Go uses **implicit** interfaces. If a struct has the right methods, it satisfies the interface automatically. No `implements` keyword needed.

### 3.4 Struct Tags = Decorators / Casts

The backtick strings after struct fields are **tags** — metadata for serializers:
```go
type Account struct {
    Name string `json:"name" db:"name"`
    //           ^-- JSON key    ^-- DB column name
}
```
- `json:"name"` = Laravel's `$casts` or API Resource field mapping
- `db:"name"` = column name mapping (like Django's `db_column`)
- `json:",omitempty"` = don't include if zero/nil (like Django's `required=False`)

### 3.5 Pointers (*string) = Nullable Fields

```go
Note *string  // Can be nil (= SQL NULL) or point to a string value
Name string   // Always has a value (empty string at minimum)
```
- `*string` = Laravel's `->nullable()` / Django's `null=True`
- `string` = Laravel's `->string('name')` (required, non-null)

### 3.6 Error Handling = Exceptions (but explicit)

Go has no try/catch. Every function that can fail returns an error:
```go
// Laravel: try { $account = Account::findOrFail($id); } catch (...) { ... }
// Django:  account = Account.objects.get(id=id)  # raises DoesNotExist
// Go:
account, err := repo.GetByID(ctx, id)
if err != nil {
    return err  // propagate the error up
}
```

### 3.7 Context (ctx) = Request Lifecycle

`context.Context` travels through every function call. It carries:
- Request cancellation (if user closes browser)
- Timeouts
- Request-scoped values

Think of it like Laravel's `$request` or Django's `request` object, but for lifecycle management.

---

## 4. The Three Layers

### Layer 1: Repository (SQL Queries)

**Like**: Eloquent query builder / Django ORM queryset methods

```go
// repository/account.go
func (r *AccountRepo) GetByID(ctx context.Context, id string) (models.Account, error) {
    row := r.db.QueryRowContext(ctx,
        `SELECT id, name, ... FROM accounts WHERE id = $1`, id)
    // Scan row into struct...
}
```

Repositories:
- Execute raw SQL (no ORM magic)
- Return model structs
- Know nothing about HTTP or business rules
- Use `$1, $2, ...` placeholders (PostgreSQL parameterized queries — prevents SQL injection)

### Layer 2: Service (Business Logic)

**Like**: Laravel Service classes / Django service layer (or fat models)

```go
// service/transaction.go
func (s *TransactionService) Create(ctx context.Context, tx models.Transaction) (...) {
    // 1. Validate the transaction
    // 2. Start a database transaction (atomic)
    // 3. Insert the transaction record
    // 4. Update the account balance
    // 5. Commit or rollback
}
```

Services:
- Contain all business rules (validation, calculations)
- Orchestrate multiple repository calls
- Handle database transactions (atomic operations)
- Know nothing about HTTP

### Layer 3: Handler (HTTP)

**Like**: Laravel Controllers / Django views

```go
// handler/pages.go
func (h *PageHandler) TransactionCreate(w http.ResponseWriter, r *http.Request) {
    // 1. Parse form data from request
    // 2. Call service to create transaction
    // 3. Render success template (or error)
}
```

Handlers:
- Parse HTTP requests (forms, JSON, URL params)
- Call services
- Render responses (HTML templates or JSON)
- Handle HTTP-specific concerns (status codes, redirects, cookies)

**Two types of handlers in this codebase:**
1. **API handlers** (`account.go`, `transaction.go`, etc.) — return JSON, like Laravel API Resources
2. **Page handlers** (`pages.go`) — return HTML via templates, like Blade views

---

## 5. Template System

### 5.1 How It Works

Go's `html/template` is similar to Blade or Django templates but simpler.

**Layout inheritance** (like `@extends('layouts.app')` in Blade):
- We use a "clone-per-page" pattern: parse shared files (layout + components + partials), then clone and add each page on top
- Each page defines `{{define "title"}}` and `{{define "content"}}` blocks
- The base layout has `{{template "content" .}}` to include the page content

**Example page** (like a Blade view):
```html
{{define "title"}}ClearMoney - Dashboard{{end}}

{{define "content"}}
<div>
    <h1>Net Worth: {{formatEGP .Data.NetWorth}}</h1>
    {{range .Data.Institutions}}
        {{template "institution-card" .}}   <!-- Like @include('partials.institution-card') -->
    {{end}}
</div>
{{end}}
```

### 5.2 Template Syntax Cheat Sheet

| Go Template              | Blade (Laravel)                    | Django Template            |
|---------------------------|------------------------------------|----------------------------|
| `{{.FieldName}}`          | `{{ $variable }}`                 | `{{ variable }}`           |
| `{{range .Items}}`        | `@foreach($items as $item)`       | `{% for item in items %}`  |
| `{{end}}`                 | `@endforeach`                     | `{% endfor %}`             |
| `{{if .Condition}}`       | `@if($condition)`                 | `{% if condition %}`       |
| `{{template "name" .}}`   | `@include('name', $data)`         | `{% include 'name' %}`     |
| `{{define "block"}}`      | `@section('block')`               | `{% block name %}`         |
| `{{formatEGP .Amount}}`   | `{{ number_format($amount) }}`    | `{{ amount\|currency }}`   |

### 5.3 HTMX (Dynamic UI without JavaScript)

Instead of a JavaScript SPA, we use **HTMX** to make parts of the page update without full reloads.

```html
<!-- When this form is submitted, POST to /institutions/add -->
<!-- and swap the response HTML into #institution-list -->
<form hx-post="/institutions/add"
      hx-target="#institution-list"
      hx-swap="innerHTML">
    <input name="name" required>
    <button type="submit">Add</button>
</form>

<div id="institution-list">
    <!-- This gets replaced with fresh HTML from the server -->
</div>
```

HTMX attributes:
- `hx-post="/url"` = Submit form via AJAX POST (like `fetch()` or `$.ajax()`)
- `hx-get="/url"` = Load content via AJAX GET
- `hx-target="#id"` = Where to put the response HTML
- `hx-swap="innerHTML"` = How to swap it (replace inner content)
- `hx-trigger="change"` = When to fire (on form change, keyup, etc.)
- `hx-confirm="Are you sure?"` = Show confirm dialog before sending

---

## 6. Database

### 6.1 Migrations

Migrations are **raw SQL files** (not an ORM schema builder). Each migration has:
- `000001_create_institutions.up.sql` — applies the change (CREATE TABLE)
- `000001_create_institutions.down.sql` — reverts it (DROP TABLE)

This is like Laravel's `Schema::create()` but written as plain SQL.

Migrations run automatically on app startup via `database/migrate.go`.

### 6.2 Why Raw SQL Instead of an ORM?

Go doesn't have a standard ORM like Eloquent or Django ORM. The ecosystem has options (GORM, sqlx) but this project uses **raw SQL** with `database/sql` because:
- Full control over queries (important for financial accuracy)
- No ORM "magic" to learn on top of Go
- Explicit is better than implicit (Go philosophy)
- Easy to debug — the SQL you write is the SQL that runs

### 6.3 Connection Pool

`database/database.go` sets up a connection pool (like Laravel's database config):
```go
db.SetMaxOpenConns(25)      // Max simultaneous connections
db.SetMaxIdleConns(5)       // Keep 5 connections warm
db.SetConnMaxLifetime(5min) // Recycle connections every 5 minutes
```

---

## 7. Authentication

### 7.1 How It Works

ClearMoney uses **PIN-based auth** (4-6 digit PIN, single user):

1. **First visit** → Redirect to `/setup` → User creates a PIN
2. **PIN stored** as bcrypt hash in `user_config` table
3. **Login** → User enters PIN → Verified against bcrypt hash
4. **Session** → Random 32-byte HMAC token stored in a cookie (30-day expiry)
5. **Every request** → Middleware checks cookie → Valid? Continue. Invalid? Redirect to `/login`

This is simpler than Laravel Sanctum or Django's session auth, but the pattern is the same:
hashed credential in DB + session token in cookie + middleware guard.

### 7.2 Middleware

```go
// Like Route::middleware('auth') in Laravel
r.Group(func(r chi.Router) {
    r.Use(authmw.Auth(authSvc))  // All routes in this group require auth
    r.Get("/", pages.Home)
    r.Get("/accounts", pages.Accounts)
    // ...
})
```

---

## 8. Testing Strategy

### Unit/Integration Tests (Go)

```bash
make test              # Fast tests (no DB needed)
make test-integration  # Slow tests (needs PostgreSQL)
```

- **Unit tests** test services with real DB (not mocks) — pragmatic approach
- **Test helpers** in `testutil/` create test data (like Laravel factories)
- Tests use `TEST_DATABASE_URL` — if not set, integration tests are skipped

### E2E Tests (Playwright)

```bash
cd e2e && npx playwright test
```

- 79 browser-based tests covering all features
- Auto-starts the Go server
- Serial execution (shared DB state)
- Tests create their own data via forms and APIs

---

## 9. Key Design Decisions

| Decision                         | Rationale                                                   |
|----------------------------------|-------------------------------------------------------------|
| **No ORM**                       | Financial app needs precise SQL control                     |
| **Server-rendered HTML + HTMX**  | Simpler than SPA, works offline with service worker          |
| **Single binary**                | Templates embedded in binary via `embed.FS` — no file deps  |
| **Atomic balance updates**       | Every transaction INSERT + balance UPDATE in one DB transaction |
| **balance_delta column**         | Each transaction stores its impact — enables easy reconciliation |
| **Clone-per-page templates**     | Go's template inheritance workaround (no native extends)    |
| **float64 for money**            | Simplified; production apps should use decimal types         |
| **PIN auth (not passwords)**     | Single-user mobile finance app — PIN is faster to type       |

---

## 10. Common Operations Cheat Sheet

### Adding a new page

1. Create template: `internal/templates/pages/my-page.html`
2. Add handler method in `handler/pages.go`
3. Add route in `handler/router.go`
4. (Optional) Add service method if business logic needed
5. (Optional) Add repository method if DB queries needed

### Adding a new API endpoint

1. Create handler file: `handler/my-resource.go`
2. Implement `Routes(r chi.Router)` method
3. Register in `router.go`: `r.Route("/api/my-resource", handler.Routes)`

### Adding a new database table

1. Create migration: `make migrate-create name=create_my_table`
2. Write SQL in the `.up.sql` and `.down.sql` files
3. Create model: `models/my_model.go`
4. Create repository: `repository/my_model.go`
5. Create service: `service/my_model.go`
6. Wire up in `router.go`

### Running the app locally

```bash
docker compose up -d          # Start PostgreSQL
make run                      # Start the Go server
# or
make build && ./server        # Build and run the binary
```
