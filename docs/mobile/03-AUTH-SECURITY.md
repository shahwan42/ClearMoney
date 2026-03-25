# ClearMoney React Native — Authentication & Security

Complete magic link auth flow, session management, rate limiting, permissions, and data isolation specification.

---

## 1. Magic Link Authentication Flow

### Unified Login/Registration Endpoint

ClearMoney uses a **single unified entry point** (`POST /login`) that auto-detects whether a user is signing in or registering.

```
┌─────────────────────────────────────────────────────────┐
│ 1. User submits email                                   │
│    POST /login { email }                                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Anti-bot checks (web only)                           │
│    - Honeypot: website field MUST be empty              │
│    - Timing: submission must take > 2 seconds           │
│    - Mobile: skip honeypot; track time client-side      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Auto-detect user status                              │
│    User exists?                                         │
│    YES → request_login_link()                           │
│    NO  → request_registration_link()                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Rate limiting checks                                 │
│    - Per-email: 5-minute cooldown                       │
│    - Per-email: max 3 per day                           │
│    - Global: max 50 per day                             │
│    ✓ Always show "check your email"                     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 5. Token generation & email send                        │
│    - Token: secrets.token_urlsafe(32) ≈ 43 chars       │
│    - TTL: 15 minutes                                    │
│    - Single-use: used=False, set True on verify        │
│    - Reuse: return REUSED if token unexpired           │
│    - Email: Resend API or stdout in dev                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 6. User clicks email link                               │
│    GET /api/auth/verify-token?token=xxx                 │
│    - Validate token (exists, not used, not expired)     │
│    - Mark token used=True (atomic, single-use)          │
│    - Login: lookup user by email                        │
│    - Registration: create user + seed 25 categories    │
│    - Create session row (user_id, token, 30-day TTL)   │
│    - Return session_token for mobile storage            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 7. Mobile: Store token & proceed                        │
│    - Save session_token in Keychain/Keystore            │
│    - Include token in Authorization header              │
│    - Navigate to home screen                            │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Token & Session Management

### AuthToken (Magic Link)

**Table:** `auth_tokens`

| Field | Value |
|-------|-------|
| Token | `secrets.token_urlsafe(32)` (≈43 chars, cryptographically random) |
| TTL | 15 minutes |
| Single-Use | Marked `used=True` immediately on `/auth/verify` |
| Reuse | If unexpired + unused token exists, return REUSED (no new email) |
| Purpose | `"login"` or `"registration"` |

**Lifecycle:**
1. Created on `POST /login` (if all checks pass)
2. Reused if unexpired + unused token exists (no new email sent)
3. Validated on `GET /api/auth/verify-token?token=xxx`
4. Marked `used=True` atomically (single-use enforcement)
5. Expired tokens cleaned up via background job

---

### Session (Server-Side)

**Table:** `sessions`

| Field | Value |
|-------|-------|
| Token | `secrets.token_urlsafe(32)` (≈43 chars, cryptographically random) |
| TTL | 30 days |
| Scope | Per user (user_id FK) |
| Storage (Web) | HttpOnly cookie `clearmoney_session` |
| Storage (Mobile) | Keychain (iOS) / Keystore (Android) |
| Validation | Token + expiry check on every request |

**Lifecycle:**
1. Created on `GET /api/auth/verify-token` after token validation
2. Used on every HTTP request (middleware validation)
3. Deleted on `POST /api/logout`
4. Expires automatically after 30 days

---

## 3. Rate Limiting

### 3-Tier Rate Limiting

#### Tier 1: IP-Based (Login/Register)
**Scope:** IP address
**Limit:** 5 requests/minute
**Applies to:** `/login`, `/register`, `/auth/verify`, `/logout`

**Behavior:** HTTP 429 if exceeded

#### Tier 2: Per-Email Limits (Magic Link)
**Scope:** Email address (normalized via `lower()`)

| Limit | Duration | Impact |
|-------|----------|--------|
| **Cooldown** | 5 minutes | Max 1 token per email every 5 minutes |
| **Daily limit** | 24 hours | Max 3 tokens per email per day |
| **Global cap** | 24 hours | Max 50 email sends per day (all users) |

**Result Codes:**
- `SENT` — token generated + email sent
- `REUSED` — unexpired token exists; no new email
- `COOLDOWN` — within 5-min window; user-facing message
- `DAILY_LIMIT` — exceeded 3/day per email
- `GLOBAL_CAP` — system at capacity (50/day exceeded)

**User-Facing Messages:**
```python
{
  SendResult.REUSED: "A sign-in link was already sent. Check your inbox.",
  SendResult.COOLDOWN: "Please wait a few minutes before requesting another link.",
  SendResult.DAILY_LIMIT: "You've reached the daily limit. Try again tomorrow.",
  SendResult.GLOBAL_CAP: "Our email system is temporarily at capacity. Try again later.",
}
```

#### Tier 3: Authenticated User API
**Scope:** User ID (or IP if unauthenticated)

| Endpoint Type | Limit |
|---------------|-------|
| JSON API (`/api/*`) | 60 req/min |
| HTML pages | 120 req/min |

**Behavior:** HTTP 429 if exceeded; include `Retry-After` header

---

## 4. Per-User Data Isolation

### Scoped Every Query

**Every table except `ExchangeRateLog` includes `user_id`.** All queries must filter:

```sql
SELECT * FROM transactions WHERE user_id = ? AND date >= ?
SELECT * FROM accounts WHERE user_id = ? AND is_dormant = false
SELECT * FROM categories WHERE user_id = ? AND is_archived = false
```

### UserScopedManager Pattern

Custom Django manager prevents accidental data leaks:

```python
class UserScopedManager(models.Manager):
    def for_user(self, user_id: UUID) -> QuerySet:
        return self.filter(user_id=user_id)
```

**Service Layer Usage:**
```python
# ✓ Correct — filtered by user_id
accounts = Account.objects.for_user(request.user_id)

# ✗ Wrong — leaks other users' data
accounts = Account.objects.all()
```

### Ownership Validation

For dangerous operations (delete, transfer), backend always validates ownership:

```python
# Example: Delete transaction
account = Account.objects.for_user(user_id).get(id=account_id)
transaction = account.transactions.get(id=tx_id)  # Already scoped by account
transaction.delete()  # Safe — user is the owner
```

**Rule:** Never trust the client. Always:
1. Look up resource filtered by `request.user_id`
2. Verify FK relationships (e.g., transaction.account_id is owned by user)
3. Perform operation only if owned

---

## 5. Authentication Middleware

### GoSessionAuthMiddleware

**File:** `backend/core/middleware.py`

**Behavior:**

```python
class GoSessionAuthMiddleware:
    """
    Validates the session cookie on every request.
    Sets request.user_id and request.user_email for authenticated users.
    Redirects to /login for unauthenticated requests to protected paths.
    """

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path

        # Skip auth for public paths
        if any(path == p or path.startswith(p) for p in PUBLIC_PATHS):
            return self.get_response(request)

        # Read session cookie (or Authorization header for mobile)
        token = self._get_token(request)
        if not token:
            return HttpResponseRedirect("/login")

        # Validate session against database
        session = Session.objects.select_related("user").filter(
            token=token,
            expires_at__gt=django_tz.now()
        ).first()

        if not session:
            response = HttpResponseRedirect("/login")
            response.delete_cookie("clearmoney_session")
            return response

        # Set authenticated attributes
        request.user_id = str(session.user_id)
        request.user_email = session.user.email

        return self.get_response(request)

    def _get_token(self, request):
        # Try cookie first (web)
        token = request.COOKIES.get("clearmoney_session", "")
        if token:
            return token

        # Try Authorization header (mobile)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix

        return None
```

**Key Behaviors:**
- Session lookup uses `select_related("user")` to minimize queries
- Session must not be expired: `expires_at__gt=now()`
- Invalid/expired sessions: delete stale cookie to prevent repeated lookups
- No CSRF token validation (protected by honeypot + timing + rate limits)

### Public Paths (No Auth Required)

```python
PUBLIC_PATHS = [
    "/healthz",
    "/static/",
    "/login",
    "/register",
    "/auth/verify",
    "/logout",
    "/api/session-status",
]
```

---

## 6. CSRF & Security Mechanisms

### Auth Views (No CSRF Token)

**Views:** `/login`, `/register`, `/auth/verify`, `/logout`
**Decorator:** `@csrf_exempt`

**Why safe?**
- **Honeypot:** Hidden `website` field — bots fill it, real users don't
- **Timing:** Form submission < 2 seconds rejected (bots are instant)
- **Session validation:** `/auth/verify` requires valid token (not guessable)
- **Single-use tokens:** Token marked used immediately (no replay)

**Mobile:** Skip honeypot; backend detects via API (no form submission)

### Authenticated Endpoints

**CSRF protection:** Django's built-in CSRF middleware (for HTML forms)
**Rate limiting:** `@api_rate` or `@general_rate` decorators
**Authentication:** `GoSessionAuthMiddleware` validates session cookie/Bearer token

---

## 7. Session Lifecycle

### Logout (Server-Side Invalidation)

```python
def logout(self, token: str) -> None:
    """Delete session by token (server-side logout)."""
    deleted, _ = Session.objects.filter(token=token).delete()
```

**Process:**
1. Read session token (cookie or Authorization header)
2. Delete matching session row from DB
3. Delete cookie from response (client also clears it)
4. Redirect to `/login`

**Security:** Session is invalidated server-side immediately (not just cookie clear)

### Multi-Device Sessions

**Current behavior:** Multiple sessions can exist for the same user.

- User A signs in on iPhone → Session #1 created
- User A signs in on iPad → Session #2 created
- Both sessions are valid and independent
- Logout deletes only the current session (from token)

**To implement "logout from all devices":**
```python
Session.objects.filter(user_id=user_id).delete()
```

---

## 8. React Native Implementation

### Session Storage

**Never store tokens in:**
- `AsyncStorage` (plaintext)
- Redux/Zustand state (lost on app restart)
- React Context (not persisted)

**Always store tokens in:**
- **iOS:** Keychain via `react-native-keychain`
- **Android:** Keystore via `react-native-encrypted-storage` or `react-native-keychain`

```javascript
// On login
const sessionToken = response.session_token;
await Keychain.setGenericPassword('clearmoney_session', sessionToken);

// On app start
const credentials = await Keychain.getGenericPassword();
if (credentials) {
  const sessionToken = credentials.password;
  // Validate token with /api/session-status
}

// On logout
await Keychain.resetGenericPassword();
```

### Authorization Header Pattern

```javascript
// Include in all API requests
const headers = {
  'Authorization': `Bearer ${sessionToken}`,
  'Content-Type': 'application/json',
};

// Example
const response = await fetch('https://api.clearmoney.app/api/accounts', {
  headers,
  method: 'GET',
});
```

### Session Timeout Warning

Call `/api/session-status` every 5 minutes to check expiry:

```javascript
useEffect(() => {
  const interval = setInterval(async () => {
    try {
      const response = await fetch('/api/session-status', {
        headers: { 'Authorization': `Bearer ${sessionToken}` },
      });

      if (!response.ok) {
        // Session expired — prompt to re-login
        handleSessionExpired();
      } else {
        const { expires_in_seconds } = await response.json();
        if (expires_in_seconds < 300) { // < 5 minutes
          showWarning(`Session expires in ${expires_in_seconds}s`);
        }
      }
    } catch (error) {
      // Network error — don't timeout
    }
  }, 5 * 60 * 1000); // 5 minutes

  return () => clearInterval(interval);
}, [sessionToken]);
```

### Deep Linking for Email Verification

React Native can't handle email links directly (would open browser).

**Solution:**

1. Email link opens browser: `https://clearmoney.app/auth/verify?token=xxx`
2. Web page sets session cookie AND detects app is installed
3. JavaScript calls deep link: `clearmoney://auth/verify?token=xxx`
4. App receives token via:
   ```javascript
   // In App.js
   const linking = {
     prefixes: ['clearmoney://', 'https://clearmoney.app/'],
     config: {
       screens: {
         AuthVerify: 'auth/verify/:token',
       },
     },
   };

   const handleDeepLink = ({ url }) => {
     const token = url.split('token=')[1];
     if (token) {
       handleAuthToken(token);
     }
   };
   ```
5. App stores token securely, navigates to home

---

## 9. Error Cases

### Login/Registration Errors

| Scenario | Response | User Message |
|----------|----------|--------------|
| Email required | 200 (form re-render) | "Email is required" |
| Honeypot filled | 200 (check_email) | Silent — shows success to confuse bots |
| Timing < 2 sec | 200 (form re-render) | Form re-displayed; no error |
| Cooldown active | 200 (check_email) | "Please wait a few minutes…" |
| 3/day limit hit | 200 (check_email) | "You've reached the daily limit…" |
| Global cap hit | 200 (check_email) | "Our email system is at capacity…" |

### Verification Errors

| Scenario | Response | Message |
|----------|----------|---------|
| Token missing | 200 (error page) | "Link is invalid or expired" |
| Token invalid | 400 | `{ "error": "Invalid token" }` |
| Token already used | 400 | `{ "error": "Link already used" }` |
| Token expired | 400 | `{ "error": "Link expired" }` |
| User not found (login) | 400 | `{ "error": "User not found" }` |

### Session Errors

| Scenario | Response | Behavior |
|----------|----------|----------|
| Session missing | 302 redirect to /login | Clear cookie if present |
| Session expired | 302 redirect to /login | Delete stale cookie |
| Session not in DB | 302 redirect to /login | Delete stale cookie |
| Rate limit exceeded | 429 | Include `Retry-After` header |

---

## 10. Security Checklist

### Token Security
- [ ] Tokens are cryptographically random (`secrets.token_urlsafe(32)` — 256-bit entropy)
- [ ] Tokens are single-use (marked `used=TRUE` on verify)
- [ ] Tokens expire (15 minutes TTL enforced via DB)
- [ ] Sessions expire (30 days TTL enforced via DB)

### Cookie Security
- [ ] HttpOnly flag set (JavaScript can't access)
- [ ] SameSite=Lax (CSRF protection)
- [ ] Secure flag set in production (HTTPS only)
- [ ] Path=/ (available site-wide)

### Data Protection
- [ ] Email enumeration prevented (login never reveals if email exists)
- [ ] Brute force protected (rate limiting on token requests)
- [ ] User isolation (all queries filter by user_id)
- [ ] Ownership validated (delete/transfer verify ownership)

### Middleware
- [ ] Middleware validates every request
- [ ] No bypass possible (public paths are explicit)
- [ ] Stale cookies deleted (prevents repeated lookups)
- [ ] Session lookup efficient (`select_related("user")`)

### API Security
- [ ] No sensitive data in logs
- [ ] Tokens never logged in plaintext
- [ ] HTTPS in production
- [ ] Passwords NOT used (magic links only)

### Mobile Security
- [ ] Tokens stored in Keychain/Keystore (not plaintext)
- [ ] Bearer token in Authorization header (not cookie)
- [ ] Session timeout warnings (before expiry)
- [ ] Deep linking handled securely

---

## 11. Production Checklist

Before going live, verify:

- [ ] Email provider configured (`RESEND_API_KEY` set)
- [ ] HTTPS enabled (`APP_URL` is https://)
- [ ] Database backups enabled
- [ ] Rate limiting tuned (`MAX_DAILY_EMAILS` matches capacity)
- [ ] Error logging enabled (unhandled exceptions logged)
- [ ] Session cleanup job running (nightly cleanup of expired tokens)
- [ ] Timezone correct (`APP_TIMEZONE` matches user base)
- [ ] Monitoring alerts set up (high rate limit hits, failed logins)
- [ ] Load testing done (system handles auth request spikes)
- [ ] Helmet.js / security headers configured (web)

---

**Generated from production Django backend on 2026-03-25**
