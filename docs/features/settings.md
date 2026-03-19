# Settings (Django)

> **Migrated to Django** — this feature is now served by the Django backend (`backend/settings_app/`). The Go handler still exists for rollback safety but is not used in production (Caddy routes `/settings` and `/export/*` to Django).

User configuration page for dark mode, CSV export, push notification subscriptions, and logout.

## Features

### Dark Mode Toggle

**Implementation:** Class-based with Tailwind CSS.

**Frontend:** `static/js/theme.js`
- IIFE that manages theme state in localStorage (key: `clearmoney-theme`)
- `getPreference()` reads from localStorage, defaults to 'light'
- `applyTheme(theme)` adds/removes `dark` class on `<html>` element
- `toggleTheme()` exposed globally for button onclick
- Theme applied before DOM renders (no flash of wrong theme)

**CSS Configuration:**
- Tailwind CDN configured with `darkMode: 'class'` in base layout
- All templates use `dark:*` prefix classes for dark overrides
- Custom overrides in `static/css/app.css` (lines ~24-50): body, backgrounds, inputs
- Chart overrides in `static/css/charts.css` (lines ~214-244): donut hole, text colors

**Template:** `pages/settings.html` — button calls `toggleTheme()` onclick

### CSV Export

**Flow:**
1. User selects date range (defaults: first of month → today)
2. GET request with `hx-boost="false"` (native browser download, not HTMX)
3. View sets `Content-Disposition: attachment` header
4. View queries transactions and streams CSV to response

**View (Django — active):** `backend/settings_app/views.py` → `export_transactions()`
**Template:** `backend/settings_app/templates/settings_app/settings.html`
**Go equivalent (rollback):** `internal/service/export.go` + `pages.go` → `ExportTransactions()`

CSV columns: Date, Type, Amount, Currency, Account ID, Category ID, Note, Created At.

### Push Notification Subscription

**Frontend:** `static/js/push.js`
- `requestNotificationPermission()` gets user consent via Notification API
- Converts VAPID public key to Uint8Array for Push Manager
- Subscribes via Push API and sends subscription to server

**Handler:** `Subscribe()` at `POST /api/push/subscribe` in `push.go`
**Template:** `pages/settings.html` — button calls `requestNotificationPermission()`

### Logout

Standard POST form (not HTMX): `POST /logout` clears session cookie and DB session, redirects to `/login`.

## Routing

| Route | Method | Backend | Purpose |
| ----- | ------ | ------- | ------- |
| `/settings` | GET | **Django** (`settings_app/views.py`) | Render settings page |
| `/export/transactions` | GET | **Django** (`settings_app/views.py`) | CSV download |
| `/logout` | POST | Go (`handler/auth.go`) | Clear session, redirect |

Caddy routes `/settings` and `/export/*` to Django. Logout still goes to Go (not yet migrated).

## Template

**File:** `backend/settings_app/templates/settings_app/settings.html`

Sections:

1. Dark mode toggle button
2. CSV export form (native download, `hx-boost="false"`)
3. Push notification subscription button
4. Logout button (POSTs to Go's `/logout`)

## Key Files

### Django (active — serves production traffic via Caddy)

| File | Purpose |
|------|---------|
| `backend/settings_app/views.py` | Settings page view + CSV export view |
| `backend/settings_app/urls.py` | URL routing for /settings, /export/transactions |
| `backend/settings_app/templates/settings_app/settings.html` | Django settings page template |
| `backend/settings_app/tests.py` | Integration tests (page rendering, CSV export, auth) |
| `backend/core/middleware.py` | GoSessionAuthMiddleware (reads Go's session cookie) |
| `backend/core/templatetags/money.py` | Template filters (format_egp, format_currency, etc.) |

### Go (retained for rollback — not used in production)

| File | Purpose |
|------|---------|
| `internal/handler/pages.go` | Settings, ExportTransactions handlers |
| `internal/handler/auth.go` | Logout handler (still used — not migrated) |
| `internal/handler/push.go` | Push subscription handler (still used — not migrated) |
| `internal/service/export.go` | CSV export service |
| `internal/templates/pages/settings.html` | Go settings page template |

### Shared

| File | Purpose |
|------|---------|
| `static/js/theme.js` | Dark mode toggle |
| `static/js/push.js` | Push notification subscription |
| `static/css/app.css` | Dark mode CSS overrides |

## For Newcomers

- **This feature is served by Django** — the Go handler exists for rollback but Caddy routes `/settings` and `/export/*` to Django in production.
- **Dark mode is class-based** — toggling adds/removes `dark` class on `<html>`. Tailwind's `dark:` prefix handles all styling.
- **Theme persists in localStorage** — not in the database. Works offline.
- **CSV export uses native download** — `hx-boost="false"` prevents HTMX from intercepting the file download.
- **Auth is magic link based** — no PINs. See `docs/features/auth.md` for details.
- **Session sharing** — Django reads Go's `clearmoney_session` cookie from the `sessions` table. No separate Django auth.

## Logging

**Django logging:**

- `page viewed: settings` — settings page rendered (INFO)
- `export.csv_downloaded` — CSV export completed with row count (INFO)
- `export: invalid date params` — bad date parameters (WARNING)

**Go logging (retained for rollback):**

- `export.csv_downloaded` — CSV export completed (row_count)

**Page views:** `settings`
