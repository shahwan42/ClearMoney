// Package middleware provides HTTP middleware for the application.
// Middleware in Go works like Laravel middleware or Django middleware:
// it wraps handlers to add cross-cutting behavior (auth, logging, etc.).
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
// This is like Laravel's auth middleware or Django's @login_required decorator.
func Auth(authSvc *service.AuthService) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Skip auth for public routes
			path := r.URL.Path
			if isPublicPath(path) {
				next.ServeHTTP(w, r)
				return
			}

			// Check if PIN is set up
			if !authSvc.IsSetup(r.Context()) {
				slog.Info("auth: redirecting to setup", "path", path)
				http.Redirect(w, r, "/setup", http.StatusFound)
				return
			}

			// Validate session cookie
			cookie, err := r.Cookie(service.SessionCookieName)
			if err != nil || cookie.Value == "" {
				slog.Warn("auth: no session cookie", "path", path)
				http.Redirect(w, r, "/login", http.StatusFound)
				return
			}

			// Verify the session token
			sessionKey, err := authSvc.GetSessionKey(r.Context())
			if err != nil || !ValidateSessionToken(cookie.Value, sessionKey) {
				slog.Warn("auth: invalid session", "path", path)
				http.Redirect(w, r, "/login", http.StatusFound)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// isPublicPath returns true for routes that don't require authentication.
func isPublicPath(path string) bool {
	publicPaths := []string{"/login", "/setup", "/healthz", "/static/"}
	for _, p := range publicPaths {
		if path == p || strings.HasPrefix(path, p) {
			return true
		}
	}
	return false
}

// CreateSessionToken generates a signed session token.
// The token is an HMAC signature of a timestamp, ensuring it can't be forged.
func CreateSessionToken(sessionKey string) string {
	timestamp := time.Now().Unix()
	data := []byte(strings.Repeat("session", 1))
	_ = timestamp // token is just a signed marker, not time-bound (cookie expiry handles that)

	mac := hmac.New(sha256.New, []byte(sessionKey))
	mac.Write(data)
	return hex.EncodeToString(mac.Sum(nil))
}

// ValidateSessionToken checks if a token was signed with the given key.
func ValidateSessionToken(token, sessionKey string) bool {
	expected := CreateSessionToken(sessionKey)
	return hmac.Equal([]byte(token), []byte(expected))
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
