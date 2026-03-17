# Rate Limiting

Per-IP rate limiting using an in-memory token bucket algorithm. Prevents brute-force login attempts, API abuse, and resource exhaustion.

## How It Works

Each IP address gets a "token bucket" that refills at a steady rate. Every request consumes one token. When the bucket is empty, the request is rejected with a 429 Too Many Requests response and a `Retry-After` header.

## Three Tiers

| Tier | Routes | Rate | Burst | Purpose |
|------|--------|------|-------|---------|
| Login | `/login`, `/register`, `/auth/verify`, `/logout` | 5/min | 5 | Prevent brute-force login attempts |
| API | `/api/*` (JSON endpoints) | 60/min | 10 | Moderate protection for API endpoints |
| General | All other authenticated pages | 120/min | 20 | Generous limit for normal browsing + HTMX |

**Exempt**: `/static/*` (assets) and `/healthz` (health check) are not rate-limited.

## Response Behavior

- **Regular requests**: Returns `429 Too Many Requests` with plain text body
- **HTMX requests** (`HX-Request: true`): Returns styled HTML error partial matching the app's design
- **Retry-After header**: Always included, indicating seconds until next allowed request

## Key Files

| File | Purpose |
|------|---------|
| `internal/middleware/ratelimit.go` | Token bucket implementation, middleware factory, IP extraction |
| `internal/middleware/ratelimit_test.go` | Unit tests for core logic, middleware, HTMX responses, IP parsing |
| `internal/handler/router.go` | Wires three limiter instances into route groups |

## Architecture

```
Request → RequestID → Logger → StructuredLogger → Recoverer
                                                      ↓
              /healthz, /static/*  ← no rate limit ←──┤
              /login, /setup       ← loginLimiter ─────┤
              /api/*               ← auth + apiLimiter ┤
              /* (pages)           ← auth + generalLimiter
```

Each `RateLimiter` instance:
- Maintains a `map[string]*tokenBucket` guarded by `sync.Mutex`
- Runs a background cleanup goroutine (every 5 min, removes entries stale for 10+ min)
- Stopped via `defer limiter.Stop()` in router.go

## Disabling for Tests

Set `DISABLE_RATE_LIMIT=true` to skip all rate limiting middleware. Used by Playwright e2e tests (configured in `e2e/playwright.config.ts` and `.github/workflows/ci.yml`) to prevent 429 errors when the full test suite runs ~300+ requests sequentially from a single IP.

## Laravel/Django Analogy

- **Laravel**: Like `Route::middleware('throttle:60,1')` or `RateLimiter::for('api', ...)` — but in-memory instead of Redis
- **Django**: Like `django-ratelimit` or DRF's `AnonRateThrottle` / `UserRateThrottle`
