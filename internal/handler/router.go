// Package handler defines HTTP handlers and routes.
// This is like Laravel's routes/web.php + Controllers, or Django's urls.py + views.py.
package handler

import (
	"database/sql"
	"log"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"

	authmw "github.com/ahmedelsamadisi/clearmoney/internal/middleware"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
	"github.com/ahmedelsamadisi/clearmoney/internal/templates"
)

// NewRouter creates the chi router with middleware and all routes.
func NewRouter(db *sql.DB) *chi.Mux {
	r := chi.NewRouter()

	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)

	r.Get("/healthz", Healthz)

	// Parse HTML templates from embedded filesystem.
	tmpl, err := ParseTemplates(templates.FS)
	if err != nil {
		log.Fatalf("parsing templates: %v", err)
	}

	// Static files
	fileServer := http.FileServer(http.Dir("static"))
	r.Handle("/static/*", http.StripPrefix("/static/", fileServer))

	if db == nil {
		pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil)
		r.Get("/", pages.Home)
		return r
	}

	// -- Database-dependent routes --

	// Repos
	institutionRepo := repository.NewInstitutionRepo(db)
	accountRepo := repository.NewAccountRepo(db)
	categoryRepo := repository.NewCategoryRepo(db)
	txRepo := repository.NewTransactionRepo(db)

	// Services
	institutionSvc := service.NewInstitutionService(institutionRepo)
	accountSvc := service.NewAccountService(accountRepo)
	categorySvc := service.NewCategoryService(categoryRepo)
	txSvc := service.NewTransactionService(txRepo, accountRepo)
	dashboardSvc := service.NewDashboardService(institutionRepo, accountRepo, txRepo)
	authSvc := service.NewAuthService(db)

	// Auth routes (public — no auth middleware)
	auth := NewAuthHandler(tmpl, authSvc)
	r.Get("/login", auth.LoginPage)
	r.Post("/login", auth.LoginSubmit)
	r.Get("/setup", auth.SetupPage)
	r.Post("/setup", auth.SetupSubmit)
	r.Post("/logout", auth.Logout)

	// Protected routes — everything below requires authentication.
	// Auth middleware redirects to /login or /setup as needed.
	r.Group(func(r chi.Router) {
		r.Use(authmw.Auth(authSvc))

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
		r.Get("/transactions", pages.Transactions)
		r.Get("/transactions/list", pages.TransactionList)
		r.Get("/transactions/new", pages.TransactionNew)
		r.Post("/transactions", pages.TransactionCreate)
		r.Get("/transactions/edit/{id}", pages.TransactionEditForm)
		r.Put("/transactions/{id}", pages.TransactionUpdate)
		r.Delete("/transactions/{id}", pages.TransactionDelete)
		r.Get("/transactions/row/{id}", pages.TransactionRow)
		r.Post("/transactions/transfer", pages.TransferCreate)
	})

	return r
}
