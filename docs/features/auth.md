# Authentication

Single-user PIN-based authentication system with bcrypt hashing and HMAC session tokens.

## Overview

ClearMoney is a single-user app. Authentication uses a 4-6 digit PIN (not username/password):

1. **First visit** → setup flow to create PIN
2. **Subsequent visits** → login with PIN
3. **Session** → 30-day cookie with HMAC token

## Setup Flow

**Route:** `GET /setup` → `POST /setup`

**Handler:** `internal/handler/auth.go` (line ~105)

1. User enters PIN + confirmation
2. Service validates PIN length (4-6 digits) and match
3. PIN hashed with `bcrypt.DefaultCost` (10 rounds)
4. Random HMAC session key generated
5. Both stored in `user_config` table
6. Session cookie created, redirect to dashboard

**Template:** `internal/templates/pages/setup.html` — bare page (no header/nav)

## Login Flow

**Route:** `GET /login` → `POST /login`

**Handler:** `internal/handler/auth.go` (line ~61)

1. If no PIN configured yet → redirect to `/setup`
2. User enters PIN
3. Service verifies via `bcrypt.CompareHashAndPassword()` (constant-time)
4. On success: HMAC session token created, 30-day cookie set
5. Redirect to dashboard

**Template:** `internal/templates/pages/login.html` — bare page

## Session Management

### HMAC Token

**File:** `internal/middleware/auth.go` (lines ~125-175)

- `CreateSessionToken()` generates SHA-256 HMAC signature using the stored session key
- `ValidateSessionToken()` verifies with constant-time comparison
- Token is identity-based (doesn't contain user data), secure against tampering

### Cookie

- Name: `clearmoney_session`
- MaxAge: 30 days
- Flags: `HttpOnly` (prevents XSS access), `SameSite=Lax` (CSRF protection)
- `SetSessionCookie()` / `ClearSessionCookie()` helpers in middleware

## Auth Middleware

**File:** `internal/middleware/auth.go` (line ~59)

The `Auth()` middleware:
1. Checks if request path is public (no auth required)
2. Reads session cookie
3. Validates HMAC token
4. If valid: attaches user context, proceeds
5. If invalid: redirects to `/setup` or `/login`

### Public Paths (no auth required)

- `/login`, `/setup` — auth pages themselves
- `/healthz` — health check endpoint
- `/static/*` — CSS, JS, images, manifest

All other routes are protected.

## Logout

**Route:** `POST /logout`

**Handler:** `internal/handler/auth.go` (line ~150)

Clears session cookie (MaxAge=-1), redirects to `/login`. Uses standard `http.Redirect` (not HTMX redirect) since the logout form is a standard POST.

## Service

**File:** `internal/service/auth.go`

| Method | Purpose |
|--------|---------|
| `Setup(ctx, pin)` | Hash PIN, generate session key, store in user_config |
| `Login(ctx, pin)` | Verify PIN, return session token |
| `VerifyPIN(ctx, pin)` | bcrypt comparison (constant-time) |
| `ChangePin(ctx, oldPin, newPin)` | Verify old, hash new, update |
| `IsConfigured(ctx)` | Check if PIN exists in user_config |

## Database

PIN hash and session key stored in `user_config` table (single row for single-user app). Created by migration 000008.

## Key Files

| File | Purpose |
|------|---------|
| `internal/handler/auth.go` | Login, Setup, Logout handlers |
| `internal/middleware/auth.go` | Auth middleware, session token creation/validation, cookie management |
| `internal/service/auth.go` | PIN hashing, verification, session logic |
| `internal/templates/pages/login.html` | Login page |
| `internal/templates/pages/setup.html` | Setup page |

## For Newcomers

- **Single-user** — there's no user table or user IDs. The `user_config` table has one row.
- **bcrypt** — same algorithm as Laravel's `Hash::make()`. Go uses `golang.org/x/crypto/bcrypt`.
- **HMAC** — the session token is an HMAC signature, not a JWT. No payload — just proof of authentication.
- **Bare pages** — login and setup templates skip the header/nav bar. They're listed in the `barePages` map in `templates.go`.
- **No HTMX** — auth forms use standard `<form method="POST">` with `http.Redirect`, not HTMX.
