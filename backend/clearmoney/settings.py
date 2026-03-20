"""
Django settings for ClearMoney.

Personal finance tracker — Django backend with PostgreSQL, HTMX, Tailwind CSS.

Like Laravel's config/ directory or Django's standard settings.py.

Key differences from a standard Django project:
- No django.contrib.admin/auth/sessions (custom magic link auth)
- Custom middleware reads session cookie from shared sessions table
- Static files served by whitenoise in production
"""

import os
from pathlib import Path

import dj_database_url

# --- Paths ---

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Security ---

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-in-production",
)
DEBUG = os.environ.get("ENV", "development") != "production"
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,0.0.0.0,127.0.0.1"
).split(",")

# --- Apps ---
# Minimal set — no admin/auth/sessions (Go owns those).
# django-htmx provides HtmxMiddleware and HTMX response classes.

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # PostgreSQL-specific fields (ArrayField, JSONField, etc.)
    "django_htmx",  # HTMX integration: request.htmx, HttpResponseClientRedirect
    "core",  # Shared: models, auth middleware, template tags
    "settings_app",  # Migrated settings feature
    "reports",  # Migrated reports feature
    "dashboard",  # Migrated dashboard (home page)
    "accounts",  # Migrated accounts & institutions
    "transactions",  # Migrated transactions, transfers, exchanges
    "people",  # Migrated people & loans
    "budgets",  # Migrated budgets
    "virtual_accounts",  # Migrated virtual accounts (envelope budgeting)
    "recurring",  # Migrated recurring rules
    "salary",  # Migrated salary distribution wizard
    "investments",  # Migrated investment portfolio tracking
    "installments",  # Migrated installment plan tracking
    "exchange_rates",  # Migrated exchange rate history
    "push",  # Migrated push notification API
    "categories",  # Category JSON API (port of Go's CategoryHandler)
    "jobs",  # Background jobs: management commands (port of Go's internal/jobs/)
    "auth_app",  # Magic link authentication (port of Go's auth handler)
]

# --- Middleware ---
# Minimal stack — GoSessionAuthMiddleware replaces Django's built-in auth.
# django-htmx's HtmxMiddleware adds request.htmx attribute.

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Serve static files in production (like Go's http.FileServer)
    "django.middleware.common.CommonMiddleware",
    "django_htmx.middleware.HtmxMiddleware",  # Adds request.htmx (bool + helpers)
    "core.middleware.GoSessionAuthMiddleware",  # Reads session cookie from shared sessions table
    "core.middleware.TimezoneMiddleware",  # Sets request.tz from APP_TIMEZONE env var
]

ROOT_URLCONF = "clearmoney.urls"

# --- Templates ---
# DIRS includes backend/templates/ for shared base.html and components.
# APP_DIRS=True enables per-app templates (settings_app/templates/, reports/templates/).

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "core.context_processors.active_tab",
            ],
        },
    },
]

WSGI_APPLICATION = "clearmoney.wsgi.application"

# --- Database ---
# Uses dj-database-url to parse DATABASE_URL (same env var the Go app uses).
# Default points to local dev PostgreSQL on port 5433 (Colima, not 5432).
# CONN_MAX_AGE=600 reuses connections for 10 minutes (like Go's sql.DB pool).

DATABASES = {
    "default": dj_database_url.config(
        default="postgres://clearmoney:clearmoney@localhost:5433/clearmoney",
        conn_max_age=600,
        # TEST NAME matches the main DB because Go owns the schema.
        # Django tests run against the real DB with --keepdb flag.
        # Without this, Django creates an empty test_clearmoney with no tables.
        test_options={"NAME": os.environ.get("TEST_DB_NAME", "clearmoney")},
    ),
}

# Django owns database migrations natively. All models live in core/models.py.

# --- Timezone ---
# Match Go app's APP_TIMEZONE for consistent date handling across both backends.

TIME_ZONE = os.environ.get("APP_TIMEZONE", "Africa/Cairo")
USE_I18N = True
USE_TZ = True
LANGUAGE_CODE = "en-us"

# --- Static files ---
# CSS, JS, manifest, service worker served by whitenoise in production.
# In Docker, static/ is copied to backend/static_src/. In dev, it's at the project root.

STATIC_URL = "/static/"
_docker_static = BASE_DIR / "static_src"
STATICFILES_DIRS = [_docker_static if _docker_static.exists() else BASE_DIR.parent / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- CSRF ---
# Exempt for now since Go handles CSRF for shared forms.
# Django-served pages use standard forms that POST to Go (e.g., logout).

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:8000",
    "https://clearmoney.shahwan.me",
]

# --- Rate Limiting ---
# django-ratelimit decorators use this cache. "default" is Django's local-memory
# cache — sufficient for single-server deployments. Like Go's token bucket middleware.
# Disabled when DISABLE_RATE_LIMIT=true (e.g., e2e test runs).

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
RATELIMIT_USE_CACHE = "default"
RATELIMIT_ENABLE = os.environ.get("DISABLE_RATE_LIMIT", "false").lower() != "true"

# --- Logging ---
# Structured logging matching Go's slog pattern: level, name, message.
# LOG_LEVEL env var controls verbosity (default: INFO).

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO").upper(),
    },
}
