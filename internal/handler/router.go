// Package handler defines HTTP handlers and routes.
// This is like Laravel's routes/web.php + Controllers, or Django's urls.py + views.py.
// Each handler is a function with the signature: func(w http.ResponseWriter, r *http.Request)
// which is Go's equivalent of a controller action.
package handler

import (
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// NewRouter creates the chi router with middleware and all routes.
// chi is a lightweight router — think of it like Laravel's Route facade
// but without the framework overhead. It implements Go's http.Handler interface.
//
// Middleware in chi works like Laravel middleware or Django middleware:
// each request passes through the middleware stack before reaching the handler.
func NewRouter() *chi.Mux {
	r := chi.NewRouter()

	// Middleware stack (runs on every request, top to bottom)
	r.Use(middleware.Logger)    // logs every request (like Laravel's logging middleware)
	r.Use(middleware.Recoverer) // catches panics and returns 500 (like exception handlers)
	r.Use(middleware.RequestID) // adds a unique X-Request-Id header for tracing

	r.Get("/healthz", Healthz)

	return r
}
