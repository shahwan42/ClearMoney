// Request-scoped structured logging middleware.
// Injects a *slog.Logger with request_id, method, and path into the context,
// so all handler logs automatically include request correlation fields.
//
// Similar to Laravel's Log::channel() context or Django's request logging middleware.
package middleware

import (
	"context"
	"log/slog"
	"net/http"

	chimw "github.com/go-chi/chi/v5/middleware"
)

type ctxKey string

const loggerKey ctxKey = "slog"

// RequestLogger middleware injects a *slog.Logger into the request context
// with request_id, method, and path fields. Place after middleware.RequestID.
func RequestLogger(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
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
// Falls back to slog.Default() if not present (e.g. in tests or non-HTTP code).
func Log(ctx context.Context) *slog.Logger {
	if logger, ok := ctx.Value(loggerKey).(*slog.Logger); ok {
		return logger
	}
	return slog.Default()
}
