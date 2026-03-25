# ClearMoney Architecture Guide

> Written for developers coming from **Laravel (PHP)** or **Django (Python)**.
> Every concept is mapped to its equivalent in those frameworks.

---

## 1. The Big Picture

ClearMoney is a **server-rendered** personal finance app. Django handles all routes.

| Concern        | Django                      | Laravel Equivalent          |
|----------------|-----------------------------|-----------------------------|
| HTTP Router    | `urls.py`                   | `routes/web.php`            |
| Controllers    | `views.py`                  | `app/Http/Controllers/`     |
| Business Logic | `services.py`               | `app/Services/`             |
| Database Layer | Django ORM                  | Eloquent Models             |
| Models         | `core/models.py`            | `app/Models/`               |
| Templates      | Django Templates            | Blade templates             |
| Migrations     | `python manage.py migrate`  | `php artisan migrate`       |
| Middleware     | `core/middleware.py`        | `app/Http/Middleware/`      |
| Config         | `clearmoney/settings.py`    | `.env` + `config/*.php`     |
| Background Jobs| Management commands         | Laravel Queues / Commands   |
| Tests          | pytest + pytest-django      | PHPUnit                     |

### Request Flow

```
Browser Request
     |
     v
Caddy                        -- TLS termination + reverse proxy
     |
     v
clearmoney/urls.py           -- Root URL routing (like routes/web.php)
     |
     v
core/middleware.py           -- GoSessionAuthMiddleware: session cookie → user_id
     |
     v
<app>/views.py               -- View function (like a Controller method)
     |
     v
<app>/services.py            -- Business logic (like a Service class)
     |
     v
Django ORM / cursor()        -- ORM queries (like Eloquent); raw SQL only for DDL/window funcs
     |
     v
PostgreSQL
     |
     v
<app>/templates/             -- Django template rendering (like Blade)
     |
     v
Browser Response
```

---

## 2. Directory Structure

```
clear-money/
|
+-- backend/                          # Django backend
|   |
|   +-- clearmoney/                   # Project package (like a Laravel bootstrap)
|   |   +-- settings.py               #   Django settings (DATABASE_URL, middleware, apps)
|   |   +-- urls.py                   #   Root URL config — includes app-level urls.py files
|   |   +-- wsgi.py                   #   WSGI entry point for gunicorn (like public/index.php)
|   |
|   +-- core/                         # Shared app: models, auth, template tags
|   |   +-- middleware.py             #   GoSessionAuthMiddleware (reads session cookie)
|   |   +-- models.py                 #   All models — ForeignKey relationships, unique constraints
|   |   +-- billing.py                #   Credit card billing cycle logic
|   |   +-- context_processors.py    #   Injects active_tab into all templates
|   |   +-- htmx.py                   #   htmx_redirect(), render_htmx_result() helpers
|   |   +-- types.py                  #   AuthenticatedRequest type alias
|   |   +-- templatetags/
|   |       +-- money.py              #   Custom filters: format_egp, format_date, neg, etc.
|   |
|   +-- auth_app/                     # Magic link auth (login, register, logout)
|   +-- dashboard/                    # Home page + HTMX partial loaders
|   +-- accounts/                     # Accounts + institutions CRUD
|   +-- transactions/                 # Transactions, transfers, exchanges, batch entry
|   +-- people/                       # People + loan tracking
|   +-- budgets/                      # Budget management
|   +-- virtual_accounts/             # Envelope budgeting
|   +-- recurring/                    # Recurring rules + sync
|   +-- investments/                  # Investment tracking
|   +-- exchange_rates/               # Exchange rates reference
|   +-- categories/                   # Category JSON API
|   +-- push/                         # Push notification API
|   +-- jobs/                         # Background jobs (management commands)
|   +-- settings_app/                 # Settings page + CSV export
|   +-- reports/                      # Reports (donut/bar charts)
|   |
|   +-- templates/                    # Shared base templates
|   |   +-- base.html                 #   Base layout with HTMX, Tailwind, nav
|   |   +-- components/               #   header.html, bottom-nav.html
|   |
|   +-- tests/
|   |   +-- factories.py              #   factory_boy model factories (like Laravel's model factories)
|   +-- conftest.py                   #   pytest fixtures: auth_user, auth_client
|   +-- pyproject.toml                #   Python dependencies + tool config
|   +-- manage.py                     #   Django management CLI (like artisan)
|   +-- Dockerfile                    #   Django container (Python 3.12 + gunicorn)
|
+-- static/                           # Static assets served at /static/
|   +-- css/app.css                   #   Custom CSS
|   +-- js/                           #   JavaScript files
|   +-- icons/                        #   PWA icons
|   +-- manifest.json                 #   PWA manifest
|
+-- e2e/                              # End-to-end tests (Playwright)
|   +-- tests/*.spec.ts               #   Browser-based tests
|
+-- docs/                             # Architecture guide, feature docs
+-- Makefile                          # Build/run shortcuts (like composer scripts)
+-- Caddyfile                         # Reverse proxy config
+-- docker-compose.yml                # Local dev environment (Django + PostgreSQL)
+-- docker-compose.prod.yml           # Production environment (Caddy + Django + PostgreSQL)
```

---

## 3. The Three Layers

### Layer 1: Models (Schema)

All models live in `backend/core/models.py`. Django manages schema via migrations.

```python
# core/models.py
class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = "accounts"
```

### Layer 2: Services (Business Logic)

**Like**: Laravel Service classes

```python
# transactions/services.py
def create_transaction(user_id: int, data: dict) -> Transaction:
    # 1. Validate
    # 2. Open DB transaction (atomic)
    # 3. INSERT transaction record
    # 4. UPDATE account balance
    # 5. Commit or rollback
```

Services:
- Contain all business rules
- Use `django.db.transaction.atomic()` for atomic operations
- Know nothing about HTTP

### Layer 3: Views (HTTP)

**Like**: Laravel Controllers

```python
# transactions/views.py
def transaction_create(request: AuthenticatedRequest) -> HttpResponse:
    # 1. Parse form data
    # 2. Call service
    # 3. Return HTMX partial or redirect
```

Views:
- Parse HTTP requests
- Call services
- Render Django templates or return HTMX fragments

---

## 4. Template System

### Layout Inheritance

Templates use Django's standard `{% extends %}` and `{% block %}`:

```html
<!-- transactions/templates/transactions/list.html -->
{% extends "base.html" %}

{% block title %}Transactions{% endblock %}

{% block content %}
<div>
    {% for tx in transactions %}
        {% include "transactions/_row.html" with tx=tx %}
    {% endfor %}
</div>
{% endblock %}
```

### HTMX (Dynamic UI without JavaScript)

```html
<!-- When this form is submitted, POST and swap the result into #tx-list -->
<form hx-post="{% url 'transaction_create' %}"
      hx-target="#tx-list"
      hx-swap="afterbegin">
    <input name="amount" required>
    <button type="submit">Add</button>
</form>

<div id="tx-list">
    <!-- Gets updated with fresh HTML from the server -->
</div>
```

HTMX attributes:
- `hx-post="/url"` = Submit via AJAX POST
- `hx-get="/url"` = Load content via AJAX GET
- `hx-target="#id"` = Where to put the response HTML
- `hx-swap="innerHTML"` = How to swap it
- `hx-trigger="change"` = When to fire
- `hx-confirm="Are you sure?"` = Confirm dialog before sending

### Template Filters (`core/templatetags/money.py`)

| Filter                    | Example                        | Output           |
|---------------------------|--------------------------------|------------------|
| `format_egp`              | `{{ amount\|format_egp }}`     | `EGP 1,234.56`   |
| `format_usd`              | `{{ amount\|format_usd }}`     | `$1,234.56`      |
| `format_date`             | `{{ date\|format_date }}`      | `Mar 2, 2026`    |
| `neg`                     | `{{ amount\|neg }}`            | negated value    |
| `percentage`              | `{{ part\|percentage:total }}` | `42.5`           |
| `chart_color`             | `{{ i\|chart_color }}`         | CSS color string |
| `conic_gradient`          | `{{ segments\|conic_gradient }}`| CSS gradient    |

---

## 5. Database

### Migrations

Django manages the schema. All models are in `core/models.py` (all with `managed=True`).

```bash
make makemigrations   # Generate migration files
make migrate          # Apply pending migrations
```

### ORM vs Raw SQL

The codebase primarily uses the Django ORM. Raw SQL via `connection.cursor()` is reserved for two cases with no ORM equivalent:

- **Window functions** — `transactions/services/crud.py` uses `SUM() OVER (PARTITION BY ...)` for running balance calculations
- **DDL** — `jobs/services/refresh_views.py` runs `REFRESH MATERIALIZED VIEW CONCURRENTLY`

Everything else (reports aggregations, dashboard stats, CRUD) uses Django ORM.

All monetary values use `NUMERIC(15,2)`. Balance updates are atomic — every transaction INSERT and balance UPDATE happen in a single DB transaction.

### Connection Pool

Configured in `settings.py`:
```python
DATABASES = {
    "default": dj_database_url.parse(
        os.environ["DATABASE_URL"],
        conn_max_age=600,  # Reuse connections for 10 minutes
    )
}
```

---

## 6. Authentication

### How It Works

ClearMoney uses **magic link auth** (email → one-time link → session):

1. User enters email → magic link sent via Resend API
2. Clicking the link creates a session in the `sessions` DB table
3. Session token stored in `clearmoney_session` cookie (30-day expiry)
4. Every request → `GoSessionAuthMiddleware` reads cookie → valid? Sets `request.user_id`. Invalid? Redirect to `/login`

### Middleware (`core/middleware.py`)

```python
class GoSessionAuthMiddleware:
    def __call__(self, request):
        token = request.COOKIES.get("clearmoney_session")
        session = Session.objects.filter(token=token).first()
        if session:
            request.user_id = session.user_id
            request.user_email = session.user.email
        # Views check request.user_id — unauthenticated returns 401/redirect
```

### AuthenticatedRequest

Views that need auth use `AuthenticatedRequest` (from `core.types`) instead of `HttpRequest`:

```python
# Always annotate views with AuthenticatedRequest so mypy catches missing auth
def my_view(request: AuthenticatedRequest) -> HttpResponse:
    user_id = request.user_id  # type-safe, guaranteed present
```

---

## 7. Testing Strategy

### Unit/Integration Tests (pytest)

```bash
make test              # All tests (real DB)
make coverage          # Tests + HTML coverage report
```

- Tests run against the real PostgreSQL schema (`--reuse-db`)
- Fixtures use `factory_boy` factories in `tests/factories.py` — like Laravel model factories
- `conftest.py` provides `auth_user`, `auth_cookie`, `auth_client` fixtures

### E2E Tests (Playwright)

```bash
make test-e2e
```

- Browser-based tests in `e2e/tests/*.spec.ts`
- `helpers.ts` creates sessions directly in DB (no UI login flow needed)
- `resetDatabase()` truncates tables and seeds categories
- Serial execution (shared DB state)

---

## 8. Key Design Decisions

| Decision                         | Rationale                                                   |
|----------------------------------|-------------------------------------------------------------|
| **All models in core/models.py** | Single source of truth for schema; ForeignKey across apps   |
| **Raw SQL for aggregations**     | Financial app needs precise query control                   |
| **Server-rendered HTML + HTMX**  | Simpler than SPA, works well offline with service worker    |
| **Atomic balance updates**       | Every tx INSERT + balance UPDATE in one DB transaction      |
| **balance_delta column**         | Each transaction stores its impact — easy reconciliation    |
| **CSS-only charts**              | No Chart.js dependency; conic-gradient donuts, flexbox bars |
| **Magic link auth**              | No passwords to manage; email is the identity              |
| **Per-user data isolation**      | Every query filters `WHERE user_id = %s`                   |

---

## 9. Common Operations

### Adding a new feature

Follow TDD: write failing tests first, then implement.

1. **Model** — add to `core/models.py`, run `make makemigrations && make migrate`
2. **Service** — create `<app>/services.py` with business logic
3. **View** — add to `<app>/views.py`, register URL in `<app>/urls.py`
4. **Template** — create in `<app>/templates/<app>/`
5. **Tests** — `<app>/tests/test_services.py` and `test_views.py`

### Running the app locally

```bash
docker compose up -d db   # Start PostgreSQL
make run                  # Start Django dev server on :8000
```
