// Package logutil provides context-aware logging helpers.
//
// This package exists separately from middleware to avoid import cycles.
// The middleware package imports service (for AuthService), so service can't
// import middleware. This package has no internal dependencies beyond stdlib,
// making it safe to import from any package.
//
// # How It Works
//
// The middleware.RequestLogger stores a *slog.Logger in the request context
// using SetLogger(). Services and handlers retrieve it using Log(ctx).
// LogEvent() is a convenience wrapper for structured event logging.
//
// Laravel analogy: Like a shared Log facade that works anywhere in the app.
// Django analogy: Like Python's logging.getLogger() with request context.
package logutil

import (
	"context"
	"log/slog"
)

// ctxKey is a custom type for context keys to prevent collisions.
type ctxKey string

const loggerKey ctxKey = "slog"

// SetLogger stores a *slog.Logger in the context.
// Called by the RequestLogger middleware to inject the request-scoped logger.
func SetLogger(ctx context.Context, logger *slog.Logger) context.Context {
	return context.WithValue(ctx, loggerKey, logger)
}

// Log retrieves the request-scoped logger from context.
// Falls back to slog.Default() if not present (e.g., in tests or background jobs).
func Log(ctx context.Context) *slog.Logger {
	if logger, ok := ctx.Value(loggerKey).(*slog.Logger); ok {
		return logger
	}
	return slog.Default()
}

// LogEvent logs a structured event at Info level with automatic request correlation.
// Use this in service methods after a successful mutation to track feature usage.
//
// Convention: event names use "entity.action" format (e.g., "transaction.created").
// Only log IDs, types, and currencies — never amounts, PINs, or PII.
//
// Usage:
//
//	logutil.LogEvent(ctx, "transaction.created", "type", "expense", "currency", "EGP")
func LogEvent(ctx context.Context, event string, keysAndValues ...any) {
	attrs := make([]any, 0, len(keysAndValues)+2)
	attrs = append(attrs, "event", event)
	attrs = append(attrs, keysAndValues...)
	Log(ctx).Info("operation completed", attrs...)
}
