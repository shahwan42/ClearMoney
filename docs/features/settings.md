# Settings

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

**View:** `backend/settings_app/views.py` → `export_transactions()`
**Template:** `backend/settings_app/templates/settings_app/settings.html`

CSV columns: Date, Type, Amount, Currency, Account ID, Category ID, Note, Created At.

### Push Notification Subscription

**Frontend:** `static/js/push.js`
- `requestNotificationPermission()` gets user consent via Notification API
- Converts VAPID public key to Uint8Array for Push Manager
- Subscribes via Push API and sends subscription to server

**Handler:** `Subscribe()` at `POST /api/push/subscribe` in `backend/push/views.py`
**Template:** `pages/settings.html` — button calls `requestNotificationPermission()`

### Logout

Standard POST form (not HTMX): `POST /logout` clears session cookie and DB session, redirects to `/login`.

## Routing

| Route | Method | Purpose |
| ----- | ------ | ------- |
| `/settings` | GET | Render settings page |
| `/export/transactions` | GET | CSV download |
| `/logout` | POST | Clear session, redirect |

## Template

**File:** `backend/settings_app/templates/settings_app/settings.html`

Sections:

1. Dark mode toggle button
2. CSV export form (native download, `hx-boost="false"`)
3. Push notification subscription button
4. Logout button

## Key Files

| File | Purpose |
|------|---------|
| `backend/settings_app/views.py` | Settings page view + CSV export view |
| `backend/settings_app/urls.py` | URL routing for /settings, /export/transactions |
| `backend/settings_app/templates/settings_app/settings.html` | Settings page template |
| `backend/settings_app/tests.py` | Integration tests (page rendering, CSV export, auth) |
| `backend/core/middleware.py` | Session auth middleware |
| `backend/core/templatetags/money.py` | Template filters (format_egp, format_currency, etc.) |
| `static/js/theme.js` | Dark mode toggle |
| `static/js/push.js` | Push notification subscription |
| `static/css/app.css` | Dark mode CSS overrides |

## For Newcomers

- **Dark mode is class-based** — toggling adds/removes `dark` class on `<html>`. Tailwind's `dark:` prefix handles all styling.
- **Theme persists in localStorage** — not in the database. Works offline.
- **CSV export uses native download** — `hx-boost="false"` prevents HTMX from intercepting the file download.
- **Auth is magic link based** — no PINs. See `docs/features/auth.md` for details.
- **Session auth** — `GoSessionAuthMiddleware` reads the `clearmoney_session` cookie from the `sessions` table. No separate per-app auth.

## Logging

- `page viewed: settings` — settings page rendered (INFO)
- `export.csv_downloaded` — CSV export completed with row count (INFO)
- `export: invalid date params` — bad date parameters (WARNING)

**Page views:** `settings`
