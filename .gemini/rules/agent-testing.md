# Agent Testing Guide — ClearMoney

> How to navigate and test the app efficiently as an AI agent.

## Server Liveness Protocol (MANDATORY before every manual test)

Confirm dev server up before driving browser (Playwright MCP, manual click-through,
QA verification). Don't assume previous run still healthy — process can be killed,
hung, OOM, or DB-disconnected since last check.

Scope: per-test check, runs every time you're about to interact with the app.
Complements `delivery-checklist.md` step 5 (session-start boot) — that runs once;
this runs every time you go to the browser.

### Pre-test check (run every time)

```bash
# Liveness probe (process alive)
curl -fsS --max-time 5 http://0.0.0.0:8000/healthz || echo "DOWN"

# Readiness probe (DB + middleware reachable; expect 302 redirect to /login)
curl -fsS -o /dev/null -w '%{http_code}\n' --max-time 5 http://0.0.0.0:8000/ || echo "DOWN"
```

Decision tree:

| Liveness | Readiness | Action |
|----------|-----------|--------|
| 200 `ok` | 302 | Proceed. |
| 200 `ok` | 500 / hang | DB or middleware broken. Kill + restart. |
| refused / "DOWN" | refused | No server. Start one. |
| hang > 5s | — | Hung. Kill + restart. |

### Start a fresh server (autonomous recipe, macOS + Linux safe)

```bash
# Kill anything on :8000 (xargs without -r for macOS BSD compatibility)
PIDS=$(lsof -ti :8000 2>/dev/null); [ -n "$PIDS" ] && kill -9 $PIDS 2>/dev/null
pkill -9 -f 'manage.py runserver' 2>/dev/null || true
pkill -9 -f 'python.*runserver.*8000' 2>/dev/null || true
pkill -9 -f 'gunicorn.*clearmoney' 2>/dev/null || true

# Start in background with rate limit off (dev shortcuts need it)
DISABLE_RATE_LIMIT=true make run > /tmp/clearmoney-dev.log 2>&1 &
disown 2>/dev/null || true

# Wait up to 30s for both probes to pass
for i in $(seq 1 30); do
  L=$(curl -fsS --max-time 2 http://0.0.0.0:8000/healthz 2>/dev/null)
  R=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://0.0.0.0:8000/ 2>/dev/null)
  [ "$L" = "ok" ] && [ "$R" = "302" ] && break
  sleep 1
done

# Final confirm + dump log on failure
curl -fsS http://0.0.0.0:8000/healthz >/dev/null && \
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://0.0.0.0:8000/)" = "302" ] || \
  { echo "STARTUP FAILED — log tail:"; tail -80 /tmp/clearmoney-dev.log; exit 1; }
```

If startup fails after 30s, tail `/tmp/clearmoney-dev.log` and triage by symptom:
- `OperationalError` / `could not connect` → DB down (check `make qa-reset` or
  Postgres on the right port — see `remote-environment.md`)
- `Address already in use` → kill recipe missed a process; widen `pkill` filter
- `ImportError` / migration mismatch → run `make migrate` once

Don't loop blindly. After 2 consecutive failed restarts with the same root cause,
stop and surface the log excerpt to the user.

### Hang recovery (during a test)

If request stalls >30s or Playwright nav times out:
1. `PIDS=$(lsof -ti :8000); [ -n "$PIDS" ] && kill -9 $PIDS` — drop hung process.
2. Re-run start recipe above.
3. Re-authenticate via `/login?dev=1`, re-seed via `/dev/seed`, retry step.

### Autonomy rules

- Never ask user "is server running?" — probe it.
- Never assume stale session cookie valid after restart — re-login.
- After 2 consecutive failed restarts with same error, stop and report log excerpt.
  Don't infinite-loop.

## Authentication (The "Fast Path")

Magic links are standard but slow for agents. Use these shortcuts in local development:

1. **Instant Login:** Navigate to `/login?dev=1` to immediately authenticate as `test@clearmoney.app`.
2. **Visible Shortcut:** On the `/login` page, a "⚡ Dev Quick Login" link is visible when `DEBUG=True`.
3. **Bypass Timing:** The 2.5s anti-bot timing check is automatically bypassed when using the `?dev=1` shortcut.

## Data Readiness

Instead of creating data manually, use the seed shortcut:
*   **Seed Shortcut:** Navigate to `/dev/seed` while authenticated.
*   **Settings Link:** Click `[data-testid="dev-seed-button"]` on the `/settings` page.
*   **Result:** Populates 3 accounts, 5 categories, and basic transactions.

## Observability & Reliability

### HTMX Loading State
The app toggles a `data-htmx-loading` attribute on the `<body>` during all HTMX requests.
*   **Safe Action:** Always wait for `body:not([data-htmx-loading])` before asserting or clicking after an HTMX-triggered change.

### Navigation via `data-testid`

Always prefer these stable selectors over text-based matching:

| Element | Selector |
|---------|----------|
| **Home Tab** | `[data-testid="nav-home"]` |
| **History Tab** | `[data-testid="nav-history"]` |
| **Quick Entry (+)** | `[data-testid="nav-plus"]` |
| **Accounts Tab** | `[data-testid="nav-accounts"]` |
| **More Menu** | `[data-testid="nav-more"]` |
| **Login Email** | `[data-testid="login-email"]` |
| **Login Submit** | `[data-testid="login-submit"]` |

### More Menu Items
* `[data-testid="menu-people"]`
* `[data-testid="menu-budgets"]`
* `[data-testid="menu-pots"]`
* `[data-testid="menu-investments"]`
* `[data-testid="menu-automations"]`
* `[data-testid="menu-batch"]`
* `[data-testid="menu-reports"]`
* `[data-testid="menu-settings"]`

### Bottom Sheets
* Close button: `[data-testid="<sheet-name>-close"]` (e.g., `quick-entry-close`, `more-menu-close`)

## Common Patterns

### Creating a Transaction
1. Click `[data-testid="nav-plus"]`.
2. Fill the form in the bottom sheet.
3. Click the primary submit button (usually `button[type="submit"]`).

### Switching to Dark Mode
Navigate to `/settings` and use the theme toggle.

## Troubleshooting
* **CSRF Errors:** If you get a 403, ensure you are sending the `X-CSRFToken` header for HTMX requests (the app handles this via `hx-headers` on `<body>`).
* **Session Expiry:** Use `GET /api/session-status` to check if you're still logged in.
