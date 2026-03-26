# Web Push Notifications Setup

ClearMoney uses **Web Push Notifications with VAPID** for browser-based alerts (credit cards due, budget warnings, etc.). **No external services required** — everything is self-hosted and free.

## Architecture

```
Browser polls GET /api/push/check every page load
    ↓
Django checks conditions:
  • Credit cards due in 3 days?
  • Account health warnings?
  • Budget thresholds exceeded?
  • Recurring transactions pending?
    ↓
Returns JSON with notification payload
    ↓
Browser displays in-app banner + browser notification
```

## Setup (One-Time)

### 1. Generate VAPID Keys (Python, No Node.js Required)

```bash
# From the project root:
python backend/manage.py generate_vapid_keys
```

Output:
```
VAPID_PUBLIC_KEY=BIkxuMVYkGpBpoiWb3ysrf2NUb6h7EbHAyeCTjCwFeMRPoi7XrJoZ5StVo_HS4OrDx4e8GmLF7jEB-KPOjvjq1g
VAPID_PRIVATE_KEY=O4_xIHTjiALaXpcXVG5qyWFt37gM6Qk3Gmhr-vXVMyY
```

### 2. Add to `.env`

```env
VAPID_PUBLIC_KEY=BIkxuMVYkGpBpoiWb3ysrf2NUb6h7EbHAyeCTjCwFeMRPoi7XrJoZ5StVo_HS4OrDx4e8GmLF7jEB-KPOjvjq1g
VAPID_PRIVATE_KEY=O4_xIHTjiALaXpcXVG5qyWFt37gM6Qk3Gmhr-vXVMyY
```

**Security:** Never commit `VAPID_PRIVATE_KEY` to git. It's in `.gitignore` by default.

### 3. Restart Django

```bash
make run
```

Done! Users can now see push notifications in their browser.

---

## What VAPID Keys Are

**VAPID** = Voluntary Application Server Identification

- Two keys: public (shared) + private (secret)
- Used by browsers to verify notifications come from your server
- Generated using P-256 elliptic curve (same as WebAuthn)
- No external service calls or APIs required
- 32-byte private key + 65-byte public key, base64-encoded

The `generate_vapid_keys` command:
1. Generates a P-256 key pair using Python's `cryptography` library
2. Converts to URL-safe base64 (VAPID format)
3. Outputs ready-to-use environment variables

---

## How It Works

### Backend (Django)

**Services:** `push/services.py`
- `NotificationService.get_pending_notifications()` checks:
  - Dashboard data (credit cards, health, budgets)
  - Recurring transactions
- Returns list of notification dicts with `title`, `body`, `url`, `tag`

**API Endpoints:** `push/views.py`
- `GET /api/push/vapid-key` — returns public key to browser
- `POST /api/push/subscribe` — acknowledges browser subscription
- `GET /api/push/check` — polling endpoint (called every page load)

### Frontend (Browser)

**Permission Flow:**
1. User clicks "Enable Notifications" in settings
2. Browser requests permission popup
3. If granted, browser fetches public key via `/api/push/vapid-key`
4. Browser creates push subscription (via Service Worker)
5. Subscription is sent to server via `/api/push/subscribe` (optional storage)

**Notification Display:**
1. On each page load, `push.js` calls `/api/push/check`
2. Server returns pending notifications (if any)
3. Browser shows in-app banner at top of page
4. If permission granted, also shows browser notification

---

## Adding New Notification Types

### 1. Add Trigger to `NotificationService` (push/services.py)

```python
def get_pending_notifications(self) -> list[dict[str, str]]:
    notifications = []

    # ... existing triggers ...

    # New trigger: inventory low
    try:
        inventory = MyService(self.user_id, self.tz).get_low_inventory()
        for item in inventory:
            notifications.append({
                "title": "Low Inventory Alert",
                "body": f"{item.name} is running low",
                "url": "/inventory",
                "tag": f"inventory-{item.id}",  # dedup key
            })
    except Exception:
        logger.exception("push: failed to load inventory notifications")

    return notifications
```

### 2. Add Test

```python
# push/tests/test_services.py
def test_low_inventory_notification():
    service = NotificationService(user_id, tz)
    notifications = service.get_pending_notifications()

    assert any(n["title"] == "Low Inventory Alert" for n in notifications)
```

### 3. Run & Deploy

```bash
make test          # verify new notification works
make lint          # check for errors
git commit -m "feat: add low inventory push notification"
```

---

## Troubleshooting

**Problem:** Users not seeing browser notifications
- ✅ Check: Is `VAPID_PUBLIC_KEY` set in `.env`?
- ✅ Check: Did user grant permission ("Enable Notifications")?
- ✅ Check: Are notifications returned by `/api/push/check`?

**Problem:** "No VAPID key configured" in browser console
- Generate keys: `python manage.py generate_vapid_keys`
- Add to `.env`: `VAPID_PUBLIC_KEY=...`
- Restart Django

**Problem:** Notifications appearing in one browser but not another
- Notification permissions are per-browser (Chrome ≠ Safari)
- User needs to grant permission separately in each browser

---

## Optional: Server-Initiated Push (Future Enhancement)

Currently, ClearMoney uses **polling** (browser asks "any notifications for me?").

If you want **server-initiated push** (server pushes to idle users), you'd need:

1. Store subscriptions in database
2. Add `pywebpush` dependency
3. Call `webpush()` from background tasks

**Benefit:** Notifications even when user is offline or on another app.
**Trade-off:** More infrastructure complexity.

See: `.claude/rules/push-notifications-future.md` for detailed plan.

---

## References

- [Web Push Protocol (RFC 8030)](https://datatracker.ietf.org/doc/html/rfc8030)
- [VAPID Spec (RFC 8292)](https://datatracker.ietf.org/doc/html/rfc8292)
- [MDN: Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
