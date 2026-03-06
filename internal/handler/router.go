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
// The db parameter can be nil (when running without a database).
// When nil, database-dependent routes are not registered.
func NewRouter(db *sql.DB) *chi.Mux {
	r := chi.NewRouter()

	// Middleware stack (runs on every request, top to bottom)
	r.Use(middleware.Logger)    // logs every request
	r.Use(middleware.Recoverer) // catches panics and returns 500
	r.Use(middleware.RequestID) // adds a unique X-Request-Id header

	r.Get("/healthz", Healthz)

	// Parse HTML templates from embedded filesystem.
	tmpl, err := ParseTemplates(templates.FS)
	if err != nil {
		log.Fatalf("parsing templates: %v", err)
	}

	// Serve static files (CSS, JS, images) from the static/ directory.
	fileServer := http.FileServer(http.Dir("static"))
	r.Handle("/static/*", http.StripPrefix("/static/", fileServer))

	if db == nil {
		// Without DB: only home page with empty state
		pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil)
		r.Get("/", pages.Home)
		return r
	}

	// -- Database-dependent routes --

	// Create repos
	institutionRepo := repository.NewInstitutionRepo(db)
	accountRepo := repository.NewAccountRepo(db)
	categoryRepo := repository.NewCategoryRepo(db)
	txRepo := repository.NewTransactionRepo(db)

	// Create services
	institutionSvc := service.NewInstitutionService(institutionRepo)
	accountSvc := service.NewAccountService(accountRepo)
	categorySvc := service.NewCategoryService(categoryRepo)
	txSvc := service.NewTransactionService(txRepo, accountRepo)
	dashboardSvc := service.NewDashboardService(institutionRepo, accountRepo, txRepo)

	// API routes (JSON)
	r.Route("/api/institutions", NewInstitutionHandler(institutionSvc).Routes)
	r.Route("/api/accounts", NewAccountHandler(accountSvc).Routes)
	r.Route("/api/categories", NewCategoryHandler(categorySvc).Routes)
	r.Route("/api/transactions", NewTransactionHandler(txSvc).Routes)

	// Page routes (HTML)
	pages := NewPageHandler(tmpl, institutionSvc, accountSvc, categorySvc, txSvc, dashboardSvc)
	r.Get("/", pages.Home)
	r.Get("/accounts", pages.Accounts)
	r.Get("/accounts/form", pages.AccountForm)
	r.Get("/accounts/list", pages.InstitutionList)
	r.Get("/transactions/new", pages.TransactionNew)
	r.Post("/transactions", pages.TransactionCreate)

	return r
}
