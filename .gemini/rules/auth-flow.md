# Auth Flow — Magic Link Authentication

Two flows — **login** (existing users) and **registration** (new users) — both use magic links.

## Flow

```text
POST /login or /register
  → anti-bot checks (honeypot field "website" + timing < 2s rejected)
  → AuthService.request_login_link() / request_registration_link()
      → rate limits: 5-min cooldown · 3/day per email · 50/day global (MAX_DAILY_EMAILS)
      → token reuse: returns REUSED if unexpired token exists (no new email sent)
      → generates secrets.token_urlsafe(32), stored in auth_tokens table (TTL: 15 min)
      → sends email via Resend (or logs to stdout in dev mode — no RESEND_API_KEY)
  → always shows "check your email" page (login never reveals if email exists)

GET /auth/verify?token=xxx
  → AuthService.verify_magic_link(): validates token (not used, not expired)
  → marks token used=True immediately (single-use)
  → login: looks up existing user; registration: creates User + seeds 25 default categories
  → creates Session (secrets.token_urlsafe(32), 30-day TTL) in sessions table
  → sets clearmoney_session cookie (httponly, samesite=Lax) → redirects to /

Every subsequent request:
  → GoSessionAuthMiddleware reads clearmoney_session cookie
  → validates against sessions table (token + expires_at > now)
  → sets request.user_id and request.user_email (AuthenticatedRequest)
  → unauthenticated → redirect to /login (clears stale cookie)

POST /logout
  → deletes Session row from DB, clears cookie → redirects to /login
```

## Key Details

- `GoSessionAuthMiddleware` is a Django middleware (name is a holdover from the Go migration)
- Auth views use `@csrf_exempt` — protected by honeypot + timing instead of CSRF tokens
- Public paths (no auth required): `/healthz`, `/static/`, `/login`, `/register`, `/auth/verify`, `/logout`
- Login never reveals whether an email exists (always shows "check your email")
- Registration does reveal "already registered" — safe because user just submitted their own email
- Dev mode: set `RESEND_API_KEY=""` — magic link URLs are logged to stdout, not emailed
