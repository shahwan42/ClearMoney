# PWA (Progressive Web App)

ClearMoney is a full PWA with offline support, push notifications, and app-like behavior on mobile.

## Manifest

**File:** `static/manifest.json`

```json
{
  "name": "ClearMoney",
  "short_name": "ClearMoney",
  "display": "standalone",
  "start_url": "/",
  "theme_color": "#0f172a",
  "icons": [
    { "src": "/static/icons/icon-192.svg", "sizes": "192x192", "type": "image/svg+xml", "purpose": "any maskable" },
    { "src": "/static/icons/icon-512.svg", "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable" }
  ]
}
```

Registered in the base layout template via `<link rel="manifest">`.

## Service Worker

**File:** `static/js/sw.js`

### Caching Strategies

| Content Type | Strategy | Behavior |
|-------------|----------|----------|
| App shell (layout, CSS, icons) | Pre-cache on install | Always available offline |
| Static assets | Cache-first | Serve from cache, fallback to network |
| HTML pages | Network-first | Try network, fallback to cached version |
| Transaction POSTs | Offline queue | Returns synthetic response when offline |

### Lifecycle Events

| Event | Behavior |
|-------|----------|
| `install` | Pre-caches app shell, calls `skipWaiting()` |
| `activate` | Cleans old cache versions, claims all clients |
| `push` | Shows browser notification from server push |
| `notificationclick` | Opens relevant page on notification tap |
| `fetch` | Routes requests through caching strategies |

### Offline Transaction Queue

When offline, POST requests to transaction endpoints receive a synthetic response with `X-Offline-Queued: true` header. Transactions are queued in IndexedDB for later sync.

## Push Notifications

### VAPID Setup

Push notifications use the Web Push API with VAPID (Voluntary Application Server Identification):
- `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` env vars
- Public key served at `GET /api/push/vapid-key`

### Subscription Flow

**Frontend:** `static/js/push.js`

1. `requestNotificationPermission()` prompts user for permission
2. Converts VAPID public key to Uint8Array
3. Subscribes via Push Manager API
4. Sends subscription to `POST /api/push/subscribe`

### Notification Types

**Service:** `backend/push/services.py` — `check_notifications()`

Checks for:
- Credit card due dates (within 3 days)
- Account health warnings (below minimum balance/deposit)
- Budget threshold alerts (approaching/exceeded limits)
- Pending recurring transactions (manual-confirm rules)

### Polling

**Frontend:** `static/js/push.js` — `checkNotifications()` polls `GET /api/push/check` on page load:
- Shows in-app banner in `#notification-banner`
- Also triggers browser notification if permission granted

## Offline Support

### IndexedDB Queue

**File:** `static/js/offline.js`

- Database: `clearmoney-offline`, store: `pending_transactions`
- Functions: `openDB()`, `queueTransaction()`, `getQueuedTransactions()`, `clearQueue()`, `getPendingCount()`

When online connectivity is restored, queued transactions can be synced.

## Pull-to-Refresh

**File:** `static/js/gestures.js` (lines ~13-50)

Works on elements with `[data-pull-refresh]` attribute:
1. Detects touch drag >60px from top of page
2. Shows "Release to refresh" indicator
3. On release: calls `window.location.reload()`

## Key Files

| File | Purpose |
|------|---------|
| `static/manifest.json` | PWA manifest (name, icons, display mode) |
| `static/js/sw.js` | Service worker (caching, push, offline) |
| `static/js/push.js` | Push notification subscription + polling |
| `static/js/offline.js` | IndexedDB offline queue |
| `static/js/gestures.js` | Pull-to-refresh gesture |
| `backend/push/views.py` | VAPID key, subscribe, check endpoints |
| `backend/push/services.py` | Notification checks (CC due, health, budgets) |

## Handler Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `GET /api/push/vapid-key` | `VAPIDKey()` | Return VAPID public key |
| `POST /api/push/subscribe` | `Subscribe()` | Store push subscription |
| `GET /api/push/check` | `CheckNotifications()` | Poll for pending notifications |

## For Newcomers

- **Standalone display** — the app runs without browser chrome on mobile (like a native app).
- **Service worker caching** — the SW caches rendered HTML pages returned by Django, not template source files.
- **Polling-based notifications** — since this is a single-user app, notifications are checked via polling (on page load), not real-time WebSocket push.
- **VAPID keys** — must be set via environment variables. Without them, push notifications won't work but the app still functions.
- **Offline queue** — transactions created offline are stored in IndexedDB. The sync mechanism relies on the service worker detecting connectivity.
