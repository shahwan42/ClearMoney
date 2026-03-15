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
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"

	"github.com/ahmedelsamadisi/clearmoney/internal/logutil"
)

// RequestLogger middleware injects a *slog.Logger into the request context
// with request_id, method, and path fields. Place after chi's middleware.RequestID
// in the middleware stack so that the request ID is available.
//
// # How It Works
//
//  1. Gets the request ID from chi's RequestID middleware (upstream in the chain)
//  2. Creates a child logger with request metadata fields "baked in"
//  3. Stores the logger in the request context using logutil.SetLogger
//  4. Passes the enriched context to the next handler via r.WithContext(ctx)
//
// After this middleware runs, any handler or service can call:
//
//	middleware.Log(ctx).Info("something happened", "key", "value")
//
// And the output will automatically include request_id, method, and path.
//
// See: https://pkg.go.dev/net/http#Request.WithContext
func RequestLogger(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		logger := slog.Default().With(
			"request_id", chimw.GetReqID(r.Context()),
			"method", r.Method,
			"path", r.URL.Path,
		)
		ctx := logutil.SetLogger(r.Context(), logger)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// Log retrieves the request-scoped logger from context.
// Falls back to slog.Default() if not present (e.g., in tests, background jobs,
// or any non-HTTP code path).
//
// This is a convenience wrapper around logutil.Log for use in handlers.
// Services should use logutil.Log directly to avoid import cycles.
//
// See: https://pkg.go.dev/context#Context.Value
func Log(ctx context.Context) *slog.Logger {
	return logutil.Log(ctx)
}

// LogEvent logs a structured event at Info level with automatic request correlation.
// This is a convenience wrapper around logutil.LogEvent for use in handlers.
// Services should use logutil.LogEvent directly to avoid import cycles.
func LogEvent(ctx context.Context, event string, keysAndValues ...any) {
	logutil.LogEvent(ctx, event, keysAndValues...)
}

// StructuredLogger middleware replaces chi's built-in middleware.Logger with
// structured slog output. It captures response status, duration, bytes written,
// route pattern, HTMX detection, and device type.
//
// Must be placed AFTER RequestLogger in the middleware stack so that
// Log(r.Context()) returns the enriched logger with request_id/method/path.
//
// Skips logging for /static/* and /healthz paths to reduce noise.
//
// Laravel analogy: Like a custom middleware that logs request/response metrics,
// similar to spatie/laravel-activitylog or a custom terminate() middleware.
func StructuredLogger(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip logging for static files and health checks
		if strings.HasPrefix(r.URL.Path, "/static/") || r.URL.Path == "/healthz" {
			next.ServeHTTP(w, r)
			return
		}

		start := time.Now()

		// Wrap response writer to capture status code and bytes written.
		// chi's WrapResponseWriter intercepts WriteHeader and Write calls.
		ww := chimw.NewWrapResponseWriter(w, r.ProtoMajor)

		next.ServeHTTP(ww, r)

		// After response: compute metrics and log
		duration := time.Since(start)
		status := ww.Status()

		// Get chi's route pattern (e.g., "/accounts/{id}" not "/accounts/abc123").
		// RoutePattern() is populated after the router matches the request.
		routePattern := ""
		if rctx := chi.RouteContext(r.Context()); rctx != nil {
			routePattern = rctx.RoutePattern()
		}

		// Detect HTMX request (HX-Request header)
		isHTMX := r.Header.Get("HX-Request") == "true"

		attrs := []any{
			"status", status,
			"status_class", fmt.Sprintf("%dxx", status/100),
			"duration_ms", duration.Milliseconds(),
			"bytes", ww.BytesWritten(),
			"route", routePattern,
			"is_htmx", isHTMX,
			"device", ClassifyDevice(r.UserAgent()),
		}

		logger := Log(r.Context())
		switch {
		case status >= 500:
			logger.Error("request completed", attrs...)
		case status >= 400:
			logger.Warn("request completed", attrs...)
		default:
			logger.Info("request completed", attrs...)
		}
	})
}

// ClassifyDevice returns "mobile", "desktop", or "bot" based on User-Agent.
// Used by StructuredLogger to categorize requests for usage analytics.
func ClassifyDevice(ua string) string {
	ua = strings.ToLower(ua)
	if strings.Contains(ua, "mobile") || strings.Contains(ua, "android") {
		return "mobile"
	}
	if strings.Contains(ua, "bot") || strings.Contains(ua, "spider") || strings.Contains(ua, "crawl") {
		return "bot"
	}
	return "desktop"
}
