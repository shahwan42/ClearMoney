// Package middleware provides HTTP middleware for the ClearMoney application.
//
// # Go Middleware Pattern (for Laravel/Django developers)
//
// In Laravel, you define middleware as classes (e.g., `App\Http\Middleware\Authenticate`)
// and register them in `Kernel.php`. In Django, middleware classes implement
// `__call__` or process_request/process_response hooks and are listed in MIDDLEWARE.
//
// In Go, middleware follows a "function wrapping" pattern. A middleware is a function
// that takes an http.Handler and returns a new http.Handler that wraps the original.
// The signature is: func(next http.Handler) http.Handler
//
// This is a decorator pattern — each middleware wraps the handler like layers of an
// onion, just like Laravel's middleware pipeline or Django's middleware stack.
//
// Chi (our router) uses this exact signature for r.Use(), which is analogous to
// Laravel's Route::middleware('auth') or Django's @method_decorator(login_required).
//
// See: https://pkg.go.dev/net/http#Handler
// See: https://go-chi.io/#/pages/middleware
package middleware

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

// Auth middleware checks for a valid session cookie on protected routes.
// Unauthenticated requests are redirected to /login (or /setup if no PIN exists).
//
// # Laravel/Django Comparison
//
// This is the equivalent of:
//   - Laravel:  `Route::middleware('auth')` or the `Authenticate` middleware class
//   - Django:   `@login_required` decorator or `LoginRequiredMixin` for CBVs
//
// # Go Middleware Anatomy (the "triple-nested function" pattern)
//
// Auth returns func(http.Handler) http.Handler — this is Go's idiomatic middleware
// signature. The outer function (Auth) is a "middleware factory" that captures
// dependencies (authSvc) via closure. This is similar to how Laravel middleware
// constructors receive dependencies via DI.
//
// The triple nesting works like this:
//   1. Auth(authSvc)                    → returns the middleware (captures dependencies)
//   2. func(next http.Handler)          → receives the "next" handler in the chain
//   3. http.HandlerFunc(func(w, r))     → the actual request-handling logic
//
// When registered with chi: r.Use(middleware.Auth(authSvc))
//
// See: https://pkg.go.dev/net/http#HandlerFunc
func Auth(authSvc *service.AuthService) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Skip auth for public routes (login page, static assets, etc.)
			// This is like Laravel's $except array in middleware or Django's
			// LOGIN_URL / LOGOUT_REDIRECT_URL settings.
			path := r.URL.Path
			if isPublicPath(path) {
				next.ServeHTTP(w, r)
				return
			}

			// Check if PIN is set up — if not, redirect to first-use setup.
			// Similar to checking if User::count() === 0 in Laravel Fortify's
			// registration flow, or Django's initial superuser creation.
			if !authSvc.IsSetup(r.Context()) {
				slog.Info("auth: redirecting to setup", "path", path)
				http.Redirect(w, r, "/setup", http.StatusFound)
				return
			}

			// Validate session cookie.
			// r.Cookie() reads from the HTTP Cookie header — this is Go's equivalent
			// of Laravel's $request->cookie() or Django's request.COOKIES.get().
			// Returns http.ErrNoCookie if the cookie doesn't exist.
			//
			// See: https://pkg.go.dev/net/http#Request.Cookie
			cookie, err := r.Cookie(service.SessionCookieName)
			if err != nil || cookie.Value == "" {
				slog.Warn("auth: no session cookie", "path", path)
				http.Redirect(w, r, "/login", http.StatusFound)
				return
			}

			// Verify the session token using HMAC (see CreateSessionToken below).
			// This is like Laravel verifying the session ID against its session store,
			// or Django checking the session cookie against django_session table.
			sessionKey, err := authSvc.GetSessionKey(r.Context())
			if err != nil || !ValidateSessionToken(cookie.Value, sessionKey) {
				slog.Warn("auth: invalid session", "path", path)
				http.Redirect(w, r, "/login", http.StatusFound)
				return
			}

			// Authentication passed — call the next handler in the chain.
			// next.ServeHTTP(w, r) is the Go equivalent of return $next($request)
			// in Laravel middleware or self.get_response(request) in Django middleware.
			next.ServeHTTP(w, r)
		})
	}
}

// isPublicPath returns true for routes that don't require authentication.
// This is the equivalent of Laravel's $except property in middleware, or
// Django's LOGIN_URL exemption. Any path that starts with one of these
// prefixes is accessible without a session cookie.
func isPublicPath(path string) bool {
	publicPaths := []string{"/login", "/setup", "/healthz", "/static/"}
	for _, p := range publicPaths {
		if path == p || strings.HasPrefix(path, p) {
			return true
		}
	}
	return false
}

// CreateSessionToken generates a signed session token using HMAC-SHA256.
//
// # How HMAC Works (for developers new to cryptography)
//
// HMAC (Hash-based Message Authentication Code) creates a signature that proves
// a message was created by someone who knows the secret key. It's NOT encryption
// — it's authentication. Think of it like a wax seal on a letter: you can read
// the letter, but the seal proves who sent it.
//
// The algorithm: HMAC(key, message) → fixed-length hex string (signature)
//
// In our case:
//   - key     = sessionKey (stored in the database, unique per user)
//   - message = "session" (a fixed string — the token is identity-based, not data-based)
//   - result  = 64-character hex string (SHA-256 produces 32 bytes = 64 hex chars)
//
// This is similar to how Laravel signs cookies (Crypt::encryptString) or how
// Django's SessionMiddleware creates signed session IDs. The key difference is
// we use HMAC directly rather than a full encryption/signing framework.
//
// See: https://pkg.go.dev/crypto/hmac
// See: https://pkg.go.dev/crypto/sha256
// See: https://pkg.go.dev/encoding/hex
func CreateSessionToken(sessionKey string) string {
	timestamp := time.Now().Unix()
	data := []byte(strings.Repeat("session", 1))
	_ = timestamp // token is just a signed marker, not time-bound (cookie expiry handles that)

	// hmac.New creates a new HMAC hasher with SHA-256 and the secret key.
	// mac.Write feeds the data to be signed. mac.Sum(nil) produces the signature.
	// hex.EncodeToString converts raw bytes to a readable hex string.
	mac := hmac.New(sha256.New, []byte(sessionKey))
	mac.Write(data)
	return hex.EncodeToString(mac.Sum(nil))
}

// ValidateSessionToken checks if a token was signed with the given key.
//
// Instead of decoding the token, we re-create it from the same key and compare.
// hmac.Equal uses constant-time comparison to prevent timing attacks — this is
// critical for security. A naive == comparison leaks information about which bytes
// match, allowing attackers to guess the token byte-by-byte.
//
// This is the same approach Laravel uses for API token verification and Django
// uses for CSRF token validation (django.utils.crypto.constant_time_compare).
//
// See: https://pkg.go.dev/crypto/hmac#Equal
func ValidateSessionToken(token, sessionKey string) bool {
	expected := CreateSessionToken(sessionKey)
	return hmac.Equal([]byte(token), []byte(expected))
}

// SetSessionCookie sets the auth session cookie on the response.
//
// Cookie attributes explained:
//   - Path:     "/" means the cookie is sent on every request (not scoped to a sub-path)
//   - MaxAge:   seconds until expiry (like Laravel's SESSION_LIFETIME in minutes * 60)
//   - HttpOnly: prevents JavaScript from reading the cookie (XSS protection) —
//               same as Laravel's 'http_only' => true in config/session.php
//   - SameSite: Lax means the cookie is sent on same-site requests and top-level
//               navigations (clicking a link), but NOT on cross-site POST requests.
//               This prevents CSRF attacks. Like Laravel's 'same_site' => 'lax'.
//
// Note: we don't set Secure: true because the app runs locally over HTTP.
// In production, you'd add Secure: true to require HTTPS.
//
// See: https://pkg.go.dev/net/http#Cookie
// See: https://pkg.go.dev/net/http#SetCookie
func SetSessionCookie(w http.ResponseWriter, token string) {
	http.SetCookie(w, &http.Cookie{
		Name:     service.SessionCookieName,
		Value:    token,
		Path:     "/",
		MaxAge:   int(service.SessionMaxAge.Seconds()),
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
	})
}

// ClearSessionCookie removes the auth session cookie by setting MaxAge to -1.
// This tells the browser to delete the cookie immediately.
//
// MaxAge semantics in Go (and HTTP):
//   - MaxAge > 0:  cookie expires after this many seconds
//   - MaxAge = 0:  cookie is omitted from the Set-Cookie header (Go-specific)
//   - MaxAge < 0:  cookie is deleted immediately (browser removes it)
//
// This is like Laravel's Auth::logout() which invalidates the session, or
// Django's django.contrib.auth.logout() which flushes the session data.
//
// See: https://pkg.go.dev/net/http#Cookie (MaxAge field documentation)
func ClearSessionCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:   service.SessionCookieName,
		Value:  "",
		Path:   "/",
		MaxAge: -1,
	})
}
