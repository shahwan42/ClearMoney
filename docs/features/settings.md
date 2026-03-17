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
3. Handler sets `Content-Disposition: attachment` header
4. Service streams transactions as CSV to response writer

**Handler:** `ExportTransactions()` at `GET /export/transactions` in `pages.go`
**Service:** `internal/service/export.go` — uses Go's `encoding/csv` package
**Template:** `pages/settings.html`

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

## Handler

**File:** `internal/handler/pages.go`

| Route | Method | Purpose |
|-------|--------|---------|
| `/settings` | GET | Render settings page |
| `/export/transactions` | GET | CSV download |
| `/logout` | POST | Clear session, redirect |

## Template

**File:** `internal/templates/pages/settings.html`

Sections:

1. Dark mode toggle button
2. CSV export form (native download)
3. Push notification subscription button
4. Logout button

## Key Files

| File | Purpose |
|------|---------|
| `internal/handler/pages.go` | Settings, ExportTransactions handlers |
| `internal/handler/auth.go` | Logout handler |
| `internal/handler/push.go` | Push subscription handler |
| `internal/service/export.go` | CSV export service |
| `internal/templates/pages/settings.html` | Settings page |
| `static/js/theme.js` | Dark mode toggle |
| `static/js/push.js` | Push notification subscription |
| `static/css/app.css` | Dark mode CSS overrides |

## For Newcomers

- **Dark mode is class-based** — toggling adds/removes `dark` class on `<html>`. Tailwind's `dark:` prefix handles all styling.
- **Theme persists in localStorage** — not in the database. Works offline.
- **CSV export uses native download** — `hx-boost="false"` prevents HTMX from intercepting the file download.
- **Auth is magic link based** — no PINs. See `docs/features/auth.md` for details.

## Logging

**Service events:**

- `export.csv_downloaded` — CSV export completed (row_count)

**Page views:** `settings`
