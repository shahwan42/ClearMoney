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

### Category Management

Users can create custom expense/income categories and manage the complete list.

**View:** `backend/settings_app/views.py` — Category CRUD endpoints

**Features:**
- Create custom categories (name, type: expense/income, icon/emoji)
- Edit custom categories (rename, change icon)
- Archive (soft-delete) custom categories — hidden from UI but preserved in transaction history
- Unarchive (restore) archived categories
- System categories cannot be edited or deleted (protected by is_system flag)

**Routes:**
- `GET /settings/categories` — category management page
- `POST /settings/categories/add` — create custom category
- `POST /settings/categories/<id>/update` — edit custom category
- `POST /settings/categories/<id>/archive` — soft-delete category
- `POST /settings/categories/<id>/unarchive` — restore archived category

**Template:** `backend/settings_app/templates/settings_app/categories.html`

Sections:
1. Create form (category name, type selector, icon input)
2. System categories list (read-only)
3. Custom categories list (with edit + archive/unarchive buttons)

**Service:** `CategoryService` in `backend/categories/services.py`

### Logout

Standard POST form with optional confirmation dialog: `POST /logout` clears session cookie and DB session, redirects to `/login`.

## Routing

| Route | Method | Purpose |
| ----- | ------ | ------- |
| `/settings` | GET | Render settings page |
| `/export/transactions` | GET | CSV download |
| `/logout` | POST | Clear session, redirect |
| `/settings/categories` | GET | Category management page |
| `/settings/categories/add` | POST | Create custom category |
| `/settings/categories/<id>/update` | POST | Edit custom category |
| `/settings/categories/<id>/archive` | POST | Archive (soft-delete) category |
| `/settings/categories/<id>/unarchive` | POST | Restore archived category |

## Templates

### Settings Page

**File:** `backend/settings_app/templates/settings_app/settings.html`

Sections:

1. Dark mode toggle button
2. CSV export form (native download, `hx-boost="false"`)
3. Push notification subscription button
4. Quick links to other features (budgets, investments, recurring, virtual accounts, batch entry)
5. Logout button (with optional confirmation dialog)

### Category Management

**File:** `backend/settings_app/templates/settings_app/categories.html`

Sections:

1. Create form — category name, type selector (expense/income), icon input
2. System categories list — read-only, system badge
3. Custom categories list — with edit and archive/unarchive buttons

## Key Files

| File | Purpose |
|------|---------|
| `backend/settings_app/views.py` | Settings page view, CSV export view, category CRUD views |
| `backend/settings_app/urls.py` | URL routing for /settings, /settings/categories, /export/transactions |
| `backend/settings_app/templates/settings_app/settings.html` | Settings page template |
| `backend/settings_app/templates/settings_app/categories.html` | Category management page template |
| `backend/categories/services.py` | CategoryService — CRUD for custom categories |
| `backend/core/models.py` | Category model (per-user custom categories, system categories) |
| `backend/settings_app/tests.py` | Integration tests (page rendering, CSV export, category CRUD, auth) |
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
