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
// Chi (our router) uses this exact signature for r.Use(), which is analogous to
// Laravel's Route::middleware('auth') or Django's @method_decorator(login_required).
package middleware

import (
	"context"
	"log/slog"
	"net/http"
	"strings"

	"github.com/shahwan42/clearmoney/internal/service"
)

// contextKey is an unexported type for context keys, preventing collisions with
// keys defined in other packages. This is a Go best practice for context values.
type contextKey int

const (
	userIDKey    contextKey = iota
	userEmailKey
)

// WithUser stores the authenticated user's ID and email in the request context.
// Called by the Auth middleware after successful session validation.
func WithUser(ctx context.Context, userID, email string) context.Context {
	ctx = context.WithValue(ctx, userIDKey, userID)
	ctx = context.WithValue(ctx, userEmailKey, email)
	return ctx
}

// UserID retrieves the authenticated user's ID from the request context.
// Returns empty string if not authenticated (should never happen on protected routes).
func UserID(ctx context.Context) string {
	if id, ok := ctx.Value(userIDKey).(string); ok {
		return id
	}
	return ""
}

// UserEmail retrieves the authenticated user's email from the request context.
func UserEmail(ctx context.Context) string {
	if email, ok := ctx.Value(userEmailKey).(string); ok {
		return email
	}
	return ""
}

// Auth middleware checks for a valid session cookie on protected routes.
// Unauthenticated requests are redirected to /login.
//
// Session validation is database-backed: the cookie holds a random token,
// and the middleware looks it up in the sessions table on every request.
// This is like Laravel's "database" session driver or Django's django_session.
func Auth(authSvc *service.AuthService) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			path := r.URL.Path
			if isPublicPath(path) {
				next.ServeHTTP(w, r)
				return
			}

			// Read session cookie
			cookie, err := r.Cookie(service.SessionCookieName)
			if err != nil || cookie.Value == "" {
				slog.Warn("auth: no session cookie", "path", path)
				http.Redirect(w, r, "/login", http.StatusFound)
				return
			}

			// Validate session against database
			userID, email, err := authSvc.ValidateSession(r.Context(), cookie.Value)
			if err != nil {
				slog.Warn("auth: invalid session", "path", path, "error", err)
				ClearSessionCookie(w)
				http.Redirect(w, r, "/login", http.StatusFound)
				return
			}

			// Store user info in context for downstream handlers
			ctx := WithUser(r.Context(), userID, email)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// isPublicPath returns true for routes that don't require authentication.
func isPublicPath(path string) bool {
	publicPaths := []string{"/login", "/register", "/auth/verify", "/healthz", "/static/"}
	for _, p := range publicPaths {
		if path == p || strings.HasPrefix(path, p) {
			return true
		}
	}
	return false
}

// SetSessionCookie sets the auth session cookie on the response.
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

// ClearSessionCookie removes the auth session cookie.
func ClearSessionCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:   service.SessionCookieName,
		Value:  "",
		Path:   "/",
		MaxAge: -1,
	})
}
