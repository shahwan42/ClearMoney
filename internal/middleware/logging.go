// Request-scoped structured logging middleware.
//
// # What This Does
//
// Injects a *slog.Logger with request_id, method, and path into the request
// context, so all handler/service logs automatically include request correlation
// fields. This means every log line from a single request shares the same
// request_id, making it easy to trace a request through the system.
//
// # Laravel/Django Comparison
//
//   - Laravel:  Similar to Log::withContext(['request_id' => ...]) or using
//               the context() method on log channels. Laravel doesn't do this
//               automatically, but packages like spatie/laravel-activitylog do.
//   - Django:   Similar to adding a logging filter that injects request metadata,
//               or using django.utils.log.RequireDebugFalse with custom formatters.
//
// # Go Concepts Used
//
//   - context.WithValue: stores a value in the request context (see below)
//   - slog.Logger.With: creates a child logger with extra fields baked in
//   - chi middleware: RequestID generates a unique ID per request
//
// See: https://pkg.go.dev/log/slog (Go's structured logging, added in Go 1.21)
// See: https://pkg.go.dev/context#WithValue
package middleware

import (
	"context"
	"log/slog"
	"net/http"

	chimw "github.com/go-chi/chi/v5/middleware"
)

// ctxKey is a custom type for context keys. Go requires context keys to be
// distinct types to avoid collisions between packages. Using a plain string
// like "slog" could collide with another package storing "slog" in context.
//
// This is a Go-specific pattern — in Laravel/Django you'd just use a string
// key like $request->attributes->get('logger') or request.META['logger'].
// Go's context is stricter to prevent bugs in large codebases.
//
// See: https://pkg.go.dev/context#WithValue (the "key" paragraph)
type ctxKey string

const loggerKey ctxKey = "slog"

// RequestLogger middleware injects a *slog.Logger into the request context
// with request_id, method, and path fields. Place after chi's middleware.RequestID
// in the middleware stack so that the request ID is available.
//
// # How It Works
//
//  1. Gets the request ID from chi's RequestID middleware (upstream in the chain)
//  2. Creates a child logger with request metadata fields "baked in"
//  3. Stores the logger in the request context using context.WithValue
//  4. Passes the enriched context to the next handler via r.WithContext(ctx)
//
// After this middleware runs, any handler or service can call:
//
//	middleware.Log(ctx).Info("something happened", "key", "value")
//
// And the output will automatically include request_id, method, and path.
//
// # context.WithValue Explained
//
// context.WithValue(parent, key, value) creates a new context that wraps the
// parent and adds a key-value pair. It does NOT mutate the parent context —
// contexts are immutable in Go. This is different from Laravel's $request->merge()
// or Django's request.META assignment, which mutate the request object directly.
//
// r.WithContext(ctx) creates a shallow copy of the request with the new context.
// The original request is unchanged (important for concurrent safety).
//
// See: https://pkg.go.dev/net/http#Request.WithContext
func RequestLogger(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// slog.Default().With() creates a child logger that inherits the parent's
		// handler but adds these fields to every log entry. This is like creating
		// a scoped LogChannel in Laravel or a named logger in Python's logging module.
		logger := slog.Default().With(
			"request_id", chimw.GetReqID(r.Context()),
			"method", r.Method,
			"path", r.URL.Path,
		)
		ctx := context.WithValue(r.Context(), loggerKey, logger)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// Log retrieves the request-scoped logger from context.
// Falls back to slog.Default() if not present (e.g., in tests, background jobs,
// or any non-HTTP code path).
//
// This pattern (retrieve from context with fallback) is common in Go. It avoids
// nil pointer panics and makes the function safe to call from anywhere.
//
// Usage example in a handler or service:
//
//	func (h *MyHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
//	    middleware.Log(r.Context()).Info("processing request", "user", userID)
//	}
//
// The type assertion ctx.Value(loggerKey).(*slog.Logger) returns (value, ok).
// If the key isn't in the context or the type doesn't match, ok is false.
// This is similar to Python's dict.get() with a default, or Laravel's
// optional() helper that prevents errors on null values.
//
// See: https://pkg.go.dev/context#Context.Value
func Log(ctx context.Context) *slog.Logger {
	if logger, ok := ctx.Value(loggerKey).(*slog.Logger); ok {
		return logger
	}
	return slog.Default()
}
