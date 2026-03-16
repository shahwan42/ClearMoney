# Authentication — Magic Link (Multi-User)

Multi-user magic link authentication system using Resend email API with server-side database sessions.

## Overview

ClearMoney uses passwordless magic link authentication:

1. **Login** → enter email → receive magic link → click → logged in
2. **Registration** → enter email → receive magic link → click → account created + categories seeded
3. **Session** → 30-day cookie backed by database sessions

No passwords, no PINs. Magic links are single-use, expire in 15 minutes.

## Login Flow

**Route:** `GET /login` → `POST /login`

**Handler:** `internal/handler/auth.go`

1. User enters email address
2. Honeypot + timing check (anti-bot)
3. Service checks if user exists in `users` table
4. If user exists: generate token, send email via Resend
5. If user doesn't exist: show same "Check your email" page (prevents email enumeration)
6. No email sent for unknown addresses — zero quota cost

**Template:** `internal/templates/pages/login.html` — bare page (no header/nav)

## Registration Flow

**Route:** `GET /register` → `POST /register`

**Handler:** `internal/handler/auth.go`

1. User enters email address
2. Honeypot + timing check (anti-bot)
3. Service checks if email already registered → error if so
4. Generate registration token, send email via Resend
5. Show "Check your email" page

**Template:** `internal/templates/pages/register.html` — bare page

## Magic Link Verification

**Route:** `GET /auth/verify?token=xxx`

**Handler:** `internal/handler/auth.go`

1. Look up token in `auth_tokens` table
2. Validate: exists, not expired (15 min TTL), not already used
3. Mark token as used
4. **Login token:** find existing user → create session
5. **Registration token:** create user → seed 25 default categories → create session
6. Set session cookie, redirect to dashboard

**Template:** `internal/templates/pages/link-expired.html` — shown if token is invalid/expired

## New User Onboarding

When a registration magic link is verified:

1. User row created in `users` table
2. `CategoryRepo.SeedDefaults(ctx, userID)` inserts 25 default categories (18 expense + 7 income)
3. Session created, user redirected to dashboard (empty state with seeded categories)

**File:** `internal/repository/category.go` — `SeedDefaults` method

## Session Management

### Database Sessions

**File:** `internal/repository/session.go`

- Sessions stored in `sessions` table with `user_id`, `token`, `expires_at`
- Token: 32-byte `crypto/rand`, base64url-encoded
- Expiry: 30 days from creation
- Validated on every request by auth middleware

### Cookie

- Name: `clearmoney_session`
- MaxAge: 30 days
- Flags: `HttpOnly` (prevents XSS), `SameSite=Lax` (CSRF protection), `Secure` when HTTPS
- `SetSessionCookie()` / `ClearSessionCookie()` helpers in middleware

## Auth Middleware

**File:** `internal/middleware/auth.go`

The `Auth()` middleware:
1. Checks if request path is public (no auth required)
2. Reads session cookie
3. Calls `authSvc.ValidateSession(token)` — looks up session in DB, checks expiry
4. If valid: stores `(userID, email)` in request context via `WithUser()`
5. If invalid: redirects to `/login`

### Context Helpers

```go
authmw.UserID(r.Context())    // extract user ID from context
authmw.UserEmail(r.Context()) // extract user email from context
```

Every handler extracts `userID` and passes it through service → repository layers. All queries include `WHERE user_id = $N` for data isolation.

### Public Paths (no auth required)

- `/login`, `/register` — auth pages
- `/auth/verify` — magic link verification
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

**File:** `internal/service/email.go`

Wraps the Resend SDK. In dev mode (no `RESEND_API_KEY`), logs emails instead of sending them.

## Data Isolation (IDOR Prevention)

Every database query filters by `user_id`:

```go
// Even PK lookups filter by user_id
func (r *AccountRepo) GetByID(ctx context.Context, userID, id string) (models.Account, error) {
    // SELECT ... FROM accounts WHERE id = $1 AND user_id = $2
}
```

This prevents Insecure Direct Object Reference (IDOR) attacks — User A cannot access User B's data even if they know the UUID.

## Logout

**Route:** `POST /logout`

Deletes session from database, clears cookie, redirects to `/login`. Uses standard `http.Redirect` (not HTMX redirect).

## Expired Token/Session Cleanup

On app startup and periodically: `authSvc.CleanupExpired(ctx)` deletes expired tokens and sessions from the database.

## Database Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts (id, email, created_at, updated_at) |
| `sessions` | Server-side sessions (user_id, token, expires_at) |
| `auth_tokens` | Magic link tokens (email, token, purpose, expires_at, used) |

**Migrations:** 000027 (users, sessions, auth_tokens), 000028 (user_id on all data tables), 000029 (materialized views with user_id), 000030 (category unique index fix for multi-user)

## Key Files

| File | Purpose |
|------|---------|
| `internal/handler/auth.go` | Login, Register, Verify, Logout handlers |
| `internal/middleware/auth.go` | Auth middleware, session validation, context injection |
| `internal/service/auth.go` | Magic link flow, rate limits, token management |
| `internal/service/email.go` | Resend SDK wrapper |
| `internal/repository/user.go` | User CRUD |
| `internal/repository/session.go` | Session CRUD |
| `internal/repository/auth_token.go` | Token CRUD + rate limit queries |
| `internal/repository/category.go` | `SeedDefaults` for new user onboarding |
| `internal/templates/pages/login.html` | Login page (email form) |
| `internal/templates/pages/register.html` | Registration page |
| `internal/templates/pages/check-email.html` | "Check your email" confirmation |
| `internal/templates/pages/link-expired.html` | Expired/invalid link page |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RESEND_API_KEY` | (none) | Resend API key (dev mode if unset) |
| `EMAIL_FROM` | `noreply@clearmoney.app` | Verified sender address |
| `APP_URL` | `http://localhost:8080` | Base URL for magic links |
| `MAX_DAILY_EMAILS` | `50` | Global daily email cap |

## Logging

**Service events:**

- `auth.login_link_sent` — magic link emailed for login
- `auth.registration_link_sent` — magic link emailed for registration
- `auth.login_completed` — login magic link verified
- `auth.user_registered` — new user created via registration link
- `auth.token_reused` — existing unexpired token found (no email sent)
- `auth.logout` — user logged out

**Page views:** `login`, `register`, `check-email`, `link-expired`

## Security Checklist

| Measure | Implementation |
|---------|---------------|
| No passwords | Magic links eliminate password attacks |
| Token generation | 32-byte `crypto/rand`, base64url |
| Token expiry | 15-minute TTL, single-use |
| Session tokens | 32-byte `crypto/rand`, DB-stored, 30-day expiry |
| Cookie flags | HttpOnly + SameSite=Lax (+ Secure on HTTPS) |
| Email enumeration | Always "Check your email" regardless of account existence |
| IDOR prevention | Every query: `AND user_id = $N` |
| Email uniqueness | Case-insensitive: `UNIQUE INDEX ON LOWER(email)` |
