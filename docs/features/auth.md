# Authentication — Magic Link (Multi-User)

Multi-user magic link authentication system using Resend email API with server-side database sessions.

## Overview

ClearMoney uses passwordless magic link authentication:

1. **Unified Auth** → enter email → app auto-detects login vs registration → receive magic link → click → logged in
2. **Session** → 30-day cookie backed by database sessions
3. **Session Timeout Warning** → dashboard shows banner when session will expire within 24 hours

No passwords, no PINs. Magic links are single-use, expire in 15 minutes.

## Unified Auth Flow

**Routes:** `GET /login` and `POST /login` (unified entry point); `/register` redirects to `/login`

**View:** `backend/auth_app/views.py` — `auth_view()`

1. User enters email address
2. Honeypot + timing check (anti-bot protection)
3. Service checks if user exists in `users` table:
   - **Existing user (login):** generate token, send email via Resend
   - **New user (registration):** generate token, send email via Resend
4. Both cases show same "Check your email" page (prevents email enumeration)
5. For unknown addresses on login attempt: no email sent, same UX (zero quota cost)

**Template:** `backend/auth_app/templates/auth_app/auth.html` — bare page (no header/nav), single email form for both login and registration

**Service method:** `auth_service.request_access_link(email)` — unified entry point that internally calls `request_login_link()` or `request_registration_link()` based on user existence. Returns `(SendResult, error_msg, is_new_user)`.

## Magic Link Verification

**Route:** `GET /auth/verify?token=xxx`

**View:** `backend/auth_app/views.py` — `verify_magic_link()`

1. Look up token in `auth_tokens` table
2. Validate: exists, not expired (15 min TTL), not already used
3. Mark token as used (single-use enforcement)
4. **Login token:** find existing user → create session
5. **Registration token:** create user → seed 25 default categories → create session
6. Set session cookie, redirect to dashboard

**Template behavior:**
- If token is valid → user redirected to `/` (dashboard)
- If token is invalid/expired → show `backend/auth_app/templates/auth_app/link_expired.html`

**Confirmation page:** After submitting email, user sees `backend/auth_app/templates/auth_app/check_email.html` with conditional messaging:
- **New user (registration):** "Welcome to ClearMoney! We sent a link to activate your account."
- **Existing user (login):** "Check your email. We sent a sign-in link..."

The `is_new_user` flag is passed from the view to distinguish the UX.

## New User Onboarding

When a registration magic link is verified:

1. User row created in `users` table
2. `AuthService._seed_default_categories(user_id)` inserts 25 default categories (18 expense + 7 income)
3. Session created, user redirected to dashboard (empty state with seeded categories)

**File:** `backend/auth_app/services.py` — `_seed_default_categories` method

## Session Management

### Database Sessions

Sessions stored in `sessions` table with `user_id`, `token`, `expires_at`.

- Token: 32-byte `secrets.token_urlsafe(32)`
- Expiry: 30 days from creation
- Validated on every request by auth middleware

### Cookie

- Name: `clearmoney_session`
- MaxAge: 30 days
- Flags: `HttpOnly`, `SameSite=Lax`, `Secure` when HTTPS

## Session Timeout Warning

**Feature:** Before a session expires, the dashboard shows a warning banner alerting the user with time remaining.

**API Endpoint:** `GET /api/session-status`

Returns JSON with session expiry:
```json
{
  "expires_in_seconds": 864000
}
```

If session is expired or missing, returns 401 status.

**Frontend Implementation:** `static/js/session-warning.js`

- Checks `/api/session-status` every 5 minutes
- Threshold: shows warning when session expires within 24 hours
- First check runs 10 seconds after page load
- If session expired: shows "Your session has expired" banner with "Sign in again" link
- If session expiring soon: shows "Your session expires in X hours" with "Sign in again" link
- Banner includes dismiss button and is ARIA-compliant (`role="alert"`, `aria-live="polite"`)
- Styles for light/dark modes: amber warning, red expired state
- Loaded on authenticated pages (base template includes the script)

**Script behavior:**
- Silent network error handling (no popups on connection issues)
- `warningShown` flag prevents duplicate warnings
- Uses `fetch()` with `credentials: 'same-origin'` for secure session checking

## Auth Middleware

**File:** `backend/core/middleware.py` — `GoSessionAuthMiddleware`

1. Checks if request path is public (no auth required)
2. Reads `clearmoney_session` cookie
3. Looks up session in DB, checks expiry
4. If valid: stores `user_id` and `user_email` on `request` object
5. If invalid: redirects to `/login`

Views access auth via `request.user_id` and `request.user_email` (typed as `AuthenticatedRequest` from `core.types`).

Every view filters all queries by `user_id` for per-user data isolation.

### Public Paths (no auth required)

- `/login` — unified auth entry point (login + registration)
- `/auth/verify` — magic link verification
- `/api/session-status` — session expiry check (used by timeout warning JS)
- `/healthz` — health check endpoint
- `/static/*` — CSS, JS, images, manifest

## Email Quota Protection

Resend free tier = 100 emails/day. Aggressive rate limiting preserves quota:

| Layer | Limit | Purpose |
|-------|-------|---------|
| Token reuse | If unexpired token exists, don't send new email | Zero cost for repeat requests |
| Per-email cooldown | 1 email per 5 min | Prevent spam to one address |
| Per-email daily | 3 per address per day | Hard cap per user |
| Global daily cap | 50/day (configurable `MAX_DAILY_EMAILS`) | Leaves 50-email buffer |
| Honeypot | Hidden field — bots fill it → silent reject | No email for bots |
| Timing check | Submit < 2s → reject | No email for automated submissions |
| Login: existing users only | Unknown emails → no email sent, same UX | Zero cost for enumeration attempts |

## Email Service

**File:** `backend/auth_app/services.py` — `EmailService` class

Wraps the Resend SDK. In dev mode (no `RESEND_API_KEY`), logs emails to stdout instead of sending them.

## Data Isolation (IDOR Prevention)

Every database query filters by `user_id`:

```python
# Even PK lookups filter by user_id
def get_by_id(user_id: str, account_id: str) -> Account:
    # SELECT ... FROM accounts WHERE id = %s AND user_id = %s
```

This prevents Insecure Direct Object Reference (IDOR) attacks — User A cannot access User B's data even if they know the UUID.

## Logout

**Route:** `POST /logout`

Deletes session from database, clears cookie, redirects to `/login`. Uses standard Django redirect (not HTMX redirect).

## Expired Token/Session Cleanup

On app startup: `cleanup_sessions` management command deletes expired tokens and sessions.

## Database Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts (id, email, created_at, updated_at) |
| `sessions` | Server-side sessions (user_id, token, expires_at) |
| `auth_tokens` | Magic link tokens (email, token, purpose, expires_at, used) |

## Key Files

| File | Purpose |
|------|---------|
| `backend/auth_app/views.py` | Login, Verify, Logout views + session status API |
| `backend/auth_app/services.py` | AuthService + EmailService — magic link flow, rate limits, token management |
| `backend/core/middleware.py` | `GoSessionAuthMiddleware` — session validation, user injection |
| `backend/core/models.py` | User, Session, AuthToken models |
| `backend/auth_app/templates/auth_app/auth.html` | Unified auth page (email form for login + registration) |
| `backend/auth_app/templates/auth_app/check_email.html` | "Check your email" confirmation (conditional for new vs existing users) |
| `backend/auth_app/templates/auth_app/link_expired.html` | Expired/invalid link page |
| `backend/auth_app/templates/auth_app/bare.html` | Bare layout (extends base, no header/nav for auth pages) |
| `static/js/session-warning.js` | Session timeout warning banner — polls `/api/session-status` every 5 minutes |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RESEND_API_KEY` | (none) | Resend API key (dev mode if unset) |
| `EMAIL_FROM` | `noreply@clearmoney.app` | Verified sender address |
| `APP_URL` | `http://localhost:8000` | Base URL for magic links |
| `MAX_DAILY_EMAILS` | `50` | Global daily email cap |

## Logging

**Service events:**

- `auth.magic_link_sent` — magic link emailed (purpose: login or registration)
- `auth.user_registered` — new user created via registration link
- `auth.login_success` — magic link verified, session created
- `auth.logout` — user logged out

**Page views:** `auth`, `check-email`, `link-expired`

## Security Checklist

| Measure | Implementation |
|---------|---------------|
| No passwords | Magic links eliminate password attacks |
| Token generation | 32-byte `secrets.token_urlsafe(32)` |
| Token expiry | 15-minute TTL, single-use |
| Session tokens | 32-byte random, DB-stored, 30-day expiry |
| Cookie flags | HttpOnly + SameSite=Lax (+ Secure on HTTPS) |
| Email enumeration | Always "Check your email" regardless of account existence |
| IDOR prevention | Every query: `AND user_id = %s` |
| Email uniqueness | Case-insensitive: `UNIQUE INDEX ON LOWER(email)` |
