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

ENV = os.environ.get("ENV", "development")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-in-production",
)
if (
    ENV == "production"
    and SECRET_KEY == "django-insecure-dev-only-change-in-production"
):
    raise ValueError(
        "DJANGO_SECRET_KEY must be set in production — never use the default"
    )

DEBUG = os.environ.get("DEBUG", "").lower() == "true" if ENV == "production" else True
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,0.0.0.0,127.0.0.1"
).split(",")

# --- Apps ---
# Minimal set — no admin/auth/sessions (custom magic link auth).
# django-htmx provides HtmxMiddleware and HTMX response classes.

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # PostgreSQL-specific fields (ArrayField, JSONField, etc.)
    "django_htmx",  # HTMX integration: request.htmx, HttpResponseClientRedirect
    "core",  # Shared: models, auth middleware, template tags
    "settings_app",  # Settings page + CSV export
    "reports",  # Monthly spending + income vs expense reports
    "dashboard",  # Home page + HTMX partial loaders
    "accounts",  # Accounts + institutions CRUD
    "transactions",  # Transactions, transfers, exchanges, batch entry
    "people",  # People + loan tracking
    "budgets",  # Budget management
    "virtual_accounts",  # Envelope budgeting
    "recurring",  # Recurring rules + sync
    "investments",  # Investment portfolio tracking
    "installments",  # Installment/EMI plans
    "exchange_rates",  # Exchange rate history
    "push",  # Push notification API
    "categories",  # Category JSON API
    "jobs",  # Background jobs (management commands)
    "auth_app",  # Magic link authentication
]

# --- Middleware ---
# Minimal stack — GoSessionAuthMiddleware replaces Django's built-in auth.
# django-htmx's HtmxMiddleware adds request.htmx attribute.

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.correlation.CorrelationIdMiddleware",  # Request correlation IDs for log tracing
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Serve static files in production
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # CSRF protection — HTMX sends token via hx-headers
    "django_htmx.middleware.HtmxMiddleware",  # Adds request.htmx (bool + helpers)
    "core.middleware.GoSessionAuthMiddleware",  # Reads session cookie from the sessions table
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # X-Frame-Options: DENY
    "core.middleware.ExceptionLoggingMiddleware",  # Log unhandled 500s with request context
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
# Uses dj-database-url to parse DATABASE_URL.
# Default points to local dev PostgreSQL on port 5433 (Colima, not 5432).
# CONN_MAX_AGE=600 reuses connections for 10 minutes.

DATABASES = {
    "default": dj_database_url.config(
        default="postgres://clearmoney:clearmoney@localhost:5433/clearmoney",
        conn_max_age=600,
        # TEST NAME matches the main DB — Django tests run against the real schema
        # with --reuse-db. Without this, Django creates an empty test_clearmoney.
        test_options={"NAME": os.environ.get("TEST_DB_NAME", "clearmoney")},
    ),
}

# Django owns database migrations natively. All models live in core/models.py.

# --- Timezone ---

TIME_ZONE = os.environ.get("APP_TIMEZONE", "Africa/Cairo")
USE_I18N = True
USE_TZ = True
LANGUAGE_CODE = "en-us"

# --- Static files ---
# CSS, JS, manifest, service worker served by whitenoise in production.
# In Docker, static/ is copied to backend/static_src/. In dev, it's at the project root.

STATIC_URL = "/static/"
_docker_static = BASE_DIR / "static_src"
STATICFILES_DIRS = [
    _docker_static if _docker_static.exists() else BASE_DIR.parent / "static"
]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security Headers ---
# Production hardening — Caddy handles TLS termination, Django adds defense-in-depth headers.

SECURE_CONTENT_TYPE_NOSNIFF = True  # X-Content-Type-Options: nosniff
X_FRAME_OPTIONS = "DENY"  # Clickjacking protection

if ENV == "production":
    SECURE_HSTS_SECONDS = 31_536_000  # 1 year HSTS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )  # Trust Caddy's header
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = False  # Caddy handles TLS, Django doesn't need to redirect

# --- CSRF ---
# CsrfViewMiddleware is enabled. HTMX sends the token via hx-headers on <body>.
# Regular forms include {% csrf_token %}. Login/register use @csrf_exempt (honeypot anti-bot instead).

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "https://clearmoney.shahwan.me",
]

# --- Rate Limiting ---
# django-ratelimit decorators use this cache. "default" is Django's local-memory
# cache — sufficient for single-server deployments.
# Disabled when DISABLE_RATE_LIMIT=true (e.g., e2e test runs).

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
RATELIMIT_USE_CACHE = "default"
RATELIMIT_ENABLE = os.environ.get("DISABLE_RATE_LIMIT", "false").lower() != "true"

# --- Logging ---
# JSON structured logging in production (for Loki/Datadog), human-readable in dev.
# LOG_LEVEL env var controls verbosity (default: INFO).

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s",
            "rename_fields": {
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
        },
        "console": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if ENV == "production" else "console",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
