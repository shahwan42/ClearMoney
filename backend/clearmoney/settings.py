"""
Django settings for ClearMoney — Strangler Fig migration from Go.

This Django project runs alongside the existing Go backend. Caddy routes
specific paths (/settings, /reports, /export) to Django while Go handles
the rest. Both apps share the same PostgreSQL database.

Like Laravel's config/ directory or Django's standard settings.py,
but configured to coexist with the Go app's schema.

Key differences from a standard Django project:
- No django.contrib.admin/auth/sessions (Go owns auth)
- All models use managed=False (Go owns schema via golang-migrate)
- Custom middleware reads Go's session cookie instead of Django sessions
- Static files served by Go, not Django
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
    "django.middleware.common.CommonMiddleware",
    "django_htmx.middleware.HtmxMiddleware",  # Adds request.htmx (bool + helpers)
    "core.middleware.GoSessionAuthMiddleware",  # Reads Go's session cookie
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

# Django must NEVER manage schema — Go owns all migrations via golang-migrate.
# Setting migration modules to None prevents makemigrations/migrate from touching
# these apps' tables.
MIGRATION_MODULES = {
    "core": None,
    "settings_app": None,
    "reports": None,
    "dashboard": None,
    "accounts": None,
    "transactions": None,
    "people": None,
    "budgets": None,
    "virtual_accounts": None,
    "recurring": None,
    "salary": None,
    "investments": None,
    "installments": None,
    "categories": None,
    "jobs": None,
    "auth_app": None,
}

# --- Timezone ---
# Match Go app's APP_TIMEZONE for consistent date handling across both backends.

TIME_ZONE = os.environ.get("APP_TIMEZONE", "Africa/Cairo")
USE_I18N = True
USE_TZ = True
LANGUAGE_CODE = "en-us"

# --- Static files ---
# Django serves static files directly (CSS, JS, manifest, service worker).
# The shared static/ directory lives at the project root, one level above backend/.

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR.parent / "static"]

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
