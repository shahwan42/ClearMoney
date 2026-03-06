// Package handler defines HTTP handlers and routes.
// This is like Laravel's routes/web.php + Controllers, or Django's urls.py + views.py.
// Each handler is a function with the signature: func(w http.ResponseWriter, r *http.Request)
// which is Go's equivalent of a controller action.
package handler

import (
	"database/sql"
	"log"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"

	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
	"github.com/ahmedelsamadisi/clearmoney/internal/templates"
)

// NewRouter creates the chi router with middleware and all routes.
// chi is a lightweight router — think of it like Laravel's Route facade
// but without the framework overhead. It implements Go's http.Handler interface.
//
// Middleware in chi works like Laravel middleware or Django middleware:
// each request passes through the middleware stack before reaching the handler.
//
// The db parameter can be nil (when running without a database).
// When nil, database-dependent routes are not registered.
func NewRouter(db *sql.DB) *chi.Mux {
	r := chi.NewRouter()

	// Middleware stack (runs on every request, top to bottom)
	r.Use(middleware.Logger)    // logs every request (like Laravel's logging middleware)
	r.Use(middleware.Recoverer) // catches panics and returns 500 (like exception handlers)
	r.Use(middleware.RequestID) // adds a unique X-Request-Id header for tracing

	r.Get("/healthz", Healthz)

	// Parse HTML templates from embedded filesystem.
	// Templates are compiled into the binary — no file I/O at runtime.
	tmpl, err := ParseTemplates(templates.FS)
	if err != nil {
		log.Fatalf("parsing templates: %v", err)
	}

	// Serve static files (CSS, JS, images) from the static/ directory.
	// Like Laravel's public/ directory or Django's STATIC_URL.
	fileServer := http.FileServer(http.Dir("static"))
	r.Handle("/static/*", http.StripPrefix("/static/", fileServer))

	// Home page works without a database
	pages := NewPageHandler(tmpl, nil, nil)
	r.Get("/", pages.Home)

	// Only register database-dependent routes if DB is available.
	// This is Go's approach to dependency injection — explicit parameter passing
	// instead of a service container like Laravel's app()->make().
	if db != nil {
		// Institution routes: /api/institutions
		institutionRepo := repository.NewInstitutionRepo(db)
		institutionSvc := service.NewInstitutionService(institutionRepo)
		institutionHandler := NewInstitutionHandler(institutionSvc)

		r.Route("/api/institutions", institutionHandler.Routes)

		// Account routes: /api/accounts
		accountRepo := repository.NewAccountRepo(db)
		accountSvc := service.NewAccountService(accountRepo)
		accountHandler := NewAccountHandler(accountSvc)

		r.Route("/api/accounts", accountHandler.Routes)

		// Category routes: /api/categories
		categoryRepo := repository.NewCategoryRepo(db)
		categorySvc := service.NewCategoryService(categoryRepo)
		categoryHandler := NewCategoryHandler(categorySvc)

		r.Route("/api/categories", categoryHandler.Routes)

		// Transaction routes: /api/transactions
		txRepo := repository.NewTransactionRepo(db)
		txSvc := service.NewTransactionService(txRepo, accountRepo)
		txHandler := NewTransactionHandler(txSvc)

		r.Route("/api/transactions", txHandler.Routes)

		// Page routes that require database access
		dbPages := NewPageHandler(tmpl, institutionSvc, accountSvc)
		r.Get("/accounts", dbPages.Accounts)
		r.Get("/accounts/form", dbPages.AccountForm)
		r.Get("/accounts/list", dbPages.InstitutionList)
	}

	return r
}
