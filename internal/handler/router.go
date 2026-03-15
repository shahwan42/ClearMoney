// Package handler defines HTTP handlers and routes for the ClearMoney web application.
//
// This is like Laravel's routes/web.php + Controllers, or Django's urls.py + views.py.
// In Go, there is no built-in MVC framework — instead, you compose a router (chi) with
// handler functions that match the http.HandlerFunc signature:
//
//	func(w http.ResponseWriter, r *http.Request)
//
// Key Go concepts for PHP/Python developers:
//
//   - http.ResponseWriter (w): Like Laravel's Response or Django's HttpResponse.
//     You write headers and body to it. Unlike Laravel/Django, you don't "return" a response —
//     you write to w directly. Think of it as an output stream.
//     See: https://pkg.go.dev/net/http#ResponseWriter
//
//   - *http.Request (r): Like Laravel's Request or Django's HttpRequest.
//     Contains URL, headers, body, form data, query params, cookies, context.
//     See: https://pkg.go.dev/net/http#Request
//
//   - chi.Router: Like Laravel's Route facade or Django's urlpatterns.
//     chi is a lightweight HTTP router that supports URL parameters ({id}),
//     middleware, route groups, and sub-routers — similar to Route::group() in Laravel.
//     See: https://github.com/go-chi/chi
//
//   - Middleware: Like Laravel middleware or Django middleware classes.
//     Wraps handlers to add cross-cutting concerns (logging, auth, panic recovery).
//     In Go, middleware is a function that takes and returns http.Handler.
//
// Architecture overview:
//   - JSON API handlers (institution.go, account.go, etc.) = Laravel API controllers
//   - Page handlers (pages.go) = Laravel web controllers that return HTML views
//   - templates.go = Template engine setup (like Blade/Jinja2 configuration)
//   - response.go = Shared response helpers (like Laravel's response() helper)
//   - charts.go = Reusable CSS-only chart components (like Blade components)
package handler

import (
	"database/sql"
	"log/slog"
	"net/http"
	"os"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"

	authmw "github.com/ahmedelsamadisi/clearmoney/internal/middleware"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
	"github.com/ahmedelsamadisi/clearmoney/internal/templates"
)

// NewRouter creates the chi router with middleware and all routes.
// This is the equivalent of:
//   - Laravel: RouteServiceProvider::boot() that registers routes/web.php and routes/api.php
//   - Django: ROOT_URLCONF that points to urls.py
//
// The function wires together the full dependency graph:
//   Repository (data access) -> Service (business logic) -> Handler (HTTP layer)
// This is manual dependency injection — Go doesn't have a DI container like
// Laravel's Service Container or Django's settings. Instead, you construct
// dependencies explicitly, which makes the wiring visible and testable.
//
// See: https://go-chi.io/#/pages/routing for chi routing patterns
func NewRouter(db *sql.DB) *chi.Mux {
	// chi.NewRouter() creates a new HTTP multiplexer (router).
	// Like: $router = new Router() in Laravel, or urlpatterns = [] in Django.
	r := chi.NewRouter()

	// Middleware stack — applied to every request in order.
	// Like Laravel's $middlewareGroups['web'] or Django's MIDDLEWARE setting.
	r.Use(middleware.Logger)    // Logs each request (method, path, duration) — like Laravel's log channel
	r.Use(middleware.Recoverer) // Catches panics and returns 500 — like Laravel's exception handler
	r.Use(middleware.RequestID) // Adds X-Request-Id header — useful for tracing in logs
	r.Use(authmw.RequestLogger) // Adds structured logger to request context (custom middleware)

	// Public health check — not behind auth middleware.
	// Like Laravel's Route::get('/healthz', ...) outside the 'auth' middleware group.
	r.Get("/healthz", Healthz)

	// Parse HTML templates from embedded filesystem.
	// Go embeds template files into the binary at compile time (via //go:embed).
	// This means no file I/O at runtime — templates travel with the binary.
	// Like Laravel's Blade compilation, but done at build time.
	tmpl, err := ParseTemplates(templates.FS)
	if err != nil {
		slog.Error("failed to parse templates", "error", err)
		os.Exit(1)
	}

	// Static files — serves CSS, JS, images from the "static/" directory.
	// Like Laravel's public/ directory or Django's STATIC_URL + STATICFILES_DIRS.
	// http.StripPrefix removes "/static/" from the URL before looking up the file.
	// See: https://pkg.go.dev/net/http#FileServer
	fileServer := http.FileServer(http.Dir("static"))
	r.Handle("/static/*", http.StripPrefix("/static/", fileServer))

	// Early return for no-DB mode (used in tests and template-only rendering).
	// PageHandler is nil-safe — it renders empty-state templates when services are nil.
	if db == nil {
		pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
		r.Get("/", pages.Home)
		return r
	}

	// ---------- Database-dependent wiring ----------
	// This is where we build the dependency graph manually.
	// In Laravel, this would be done in ServiceProvider::register().
	// In Django, services are typically instantiated in views or via dependency injection libraries.

	// Repositories — data access layer (like Laravel's Eloquent models or Django's ORM managers).
	// Each repo wraps SQL queries for one database table.
	institutionRepo := repository.NewInstitutionRepo(db)
	accountRepo := repository.NewAccountRepo(db)
	categoryRepo := repository.NewCategoryRepo(db)
	txRepo := repository.NewTransactionRepo(db)

	personRepo := repository.NewPersonRepo(db)

	// Services — business logic layer (like Laravel's Service classes or Django's service layer).
	// Each service depends on one or more repositories and encapsulates domain rules.
	institutionSvc := service.NewInstitutionService(institutionRepo)
	accountSvc := service.NewAccountService(accountRepo)
	categorySvc := service.NewCategoryService(categoryRepo)
	exchangeRateRepo := repository.NewExchangeRateRepo(db)
	txSvc := service.NewTransactionService(txRepo, accountRepo)
	txSvc.SetExchangeRateRepo(exchangeRateRepo)
	personSvc := service.NewPersonService(personRepo, txRepo)
	salarySvc := service.NewSalaryService(txRepo, accountRepo)
	dashboardSvc := service.NewDashboardService(institutionRepo, accountRepo, txRepo)
	dashboardSvc.SetExchangeRateRepo(exchangeRateRepo)
	dashboardSvc.SetPersonRepo(personRepo)
	investmentRepo := repository.NewInvestmentRepo(db)
	investmentSvc := service.NewInvestmentService(investmentRepo)
	dashboardSvc.SetInvestmentRepo(investmentRepo)
	streakSvc := service.NewStreakService(db)
	dashboardSvc.SetStreakService(streakSvc)
	// Wire snapshot service for net worth sparkline (TASK-055)
	snapshotRepo := repository.NewSnapshotRepo(db)
	snapshotSvc := service.NewSnapshotService(snapshotRepo, accountRepo, institutionRepo, exchangeRateRepo)
	dashboardSvc.SetSnapshotService(snapshotSvc)
	dashboardSvc.SetDB(db)
	reportsSvc := service.NewReportsService(db)
	recurringRepo := repository.NewRecurringRepo(db)
	recurringSvc := service.NewRecurringService(recurringRepo, txSvc)
	accountSvc.SetRecurringRepo(recurringRepo) // BUG-012: clean up stale rules when account is deleted
	installmentRepo := repository.NewInstallmentRepo(db)
	installmentSvc := service.NewInstallmentService(installmentRepo, txSvc)
	notificationSvc := service.NewNotificationService(dashboardSvc, recurringSvc)
	exportSvc := service.NewExportService(txRepo)
	authSvc := service.NewAuthService(db)

	// Auth routes (public — no auth middleware).
	// Like Laravel: Route::get('/login', [AuthController::class, 'showLoginForm']);
	// These are outside the auth group so unauthenticated users can reach them.
	auth := NewAuthHandler(tmpl, authSvc)
	r.Get("/login", auth.LoginPage)
	r.Post("/login", auth.LoginSubmit)
	r.Get("/setup", auth.SetupPage)
	r.Post("/setup", auth.SetupSubmit)
	r.Post("/logout", auth.Logout)

	// Protected routes — everything below requires authentication.
	// r.Group() creates a route group with shared middleware, like:
	//   Laravel: Route::middleware('auth')->group(function () { ... })
	//   Django: decorating views with @login_required
	// Auth middleware checks the session cookie and redirects to /login or /setup as needed.
	r.Group(func(r chi.Router) {
		r.Use(authmw.Auth(authSvc))

		// API routes (JSON) — RESTful endpoints consumed by HTMX and tests.
		// r.Route() creates a sub-router at a URL prefix, like Laravel's Route::prefix().
		// The handler's Routes method registers CRUD endpoints within that prefix.
		// Example: r.Route("/api/institutions", handler.Routes) registers:
		//   GET    /api/institutions      → List
		//   POST   /api/institutions      → Create
		//   GET    /api/institutions/{id}  → Get
		//   PUT    /api/institutions/{id}  → Update
		//   DELETE /api/institutions/{id}  → Delete
		r.Route("/api/institutions", NewInstitutionHandler(institutionSvc).Routes)
		r.Route("/api/accounts", NewAccountHandler(accountSvc).Routes)
		r.Route("/api/categories", NewCategoryHandler(categorySvc).Routes)
		r.Route("/api/transactions", NewTransactionHandler(txSvc).Routes)
		r.Route("/api/persons", NewPersonHandler(personSvc).Routes)

		// Page routes (HTML) — serve full pages and HTMX partials.
		// These use form submissions (not JSON) and return HTML responses.
		// HTMX endpoints return HTML fragments that get swapped into the DOM.
		pages := NewPageHandler(tmpl, institutionSvc, accountSvc, categorySvc, txSvc, dashboardSvc, personSvc, salarySvc, reportsSvc, recurringSvc, investmentSvc, installmentSvc, exportSvc, authSvc, exchangeRateRepo)
		pages.SetSnapshotService(snapshotSvc) // TASK-059: account balance sparklines
		// TASK-062/063: Wire virtual fund service
		virtualFundRepo := repository.NewVirtualFundRepo(db)
		virtualFundSvc := service.NewVirtualFundService(virtualFundRepo)
		pages.SetVirtualFundService(virtualFundSvc)
		dashboardSvc.SetVirtualFundService(virtualFundSvc)
		// TASK-065: Wire budget service
		budgetRepo := repository.NewBudgetRepo(db)
		budgetSvc := service.NewBudgetService(budgetRepo)
		pages.SetBudgetService(budgetSvc)
		dashboardSvc.SetBudgetService(budgetSvc)
		// TASK-068: Wire account health service
		healthSvc := service.NewAccountHealthService(accountRepo, txRepo)
		pages.SetAccountHealthService(healthSvc)
		dashboardSvc.SetAccountHealthService(healthSvc)
		r.Get("/", pages.Home)
		r.Get("/partials/recent-transactions", pages.RecentTransactions)
		r.Get("/partials/people-summary", pages.PeopleSummary)
		r.Get("/accounts", pages.Accounts)
		r.Get("/accounts/form", pages.AccountForm)
		r.Get("/accounts/list", pages.InstitutionList)
		r.Get("/accounts/institution-form", pages.InstitutionFormPartial)
		r.Get("/accounts/empty", pages.EmptyPartial)
		r.Get("/accounts/{id}", pages.AccountDetail)
		r.Get("/accounts/{id}/statement", pages.CreditCardStatement)
		r.Post("/accounts/{id}/dormant", pages.ToggleDormant)
		r.Post("/accounts/{id}/health", pages.AccountHealthUpdate)
		r.Get("/accounts/{id}/edit-form", pages.AccountEditForm)
		r.Post("/accounts/{id}/edit", pages.AccountUpdate)
		r.Delete("/accounts/{id}", pages.AccountDelete)
		r.Post("/accounts/add", pages.AccountAdd)
		r.Post("/accounts/reorder", pages.ReorderAccounts)
		r.Post("/institutions/add", pages.InstitutionAdd)
		r.Post("/institutions/reorder", pages.ReorderInstitutions)
		r.Get("/institutions/{id}/edit-form", pages.InstitutionEditForm)
		r.Put("/institutions/{id}", pages.InstitutionUpdate)
		r.Get("/institutions/{id}/delete-confirm", pages.InstitutionDeleteConfirm)
		r.Delete("/institutions/{id}", pages.InstitutionDelete)
		r.Get("/transactions", pages.Transactions)
		r.Get("/transactions/list", pages.TransactionList)
		r.Get("/transactions/new", pages.TransactionNew)
		r.Get("/transactions/quick-form", pages.QuickEntryForm)
		r.Post("/transactions/quick", pages.QuickEntryCreate)
		r.Post("/transactions", pages.TransactionCreate)
		r.Get("/transactions/edit/{id}", pages.TransactionEditForm)
		r.Put("/transactions/{id}", pages.TransactionUpdate)
		r.Delete("/transactions/{id}", pages.TransactionDelete)
		r.Get("/transactions/row/{id}", pages.TransactionRow)
		r.Get("/transfers/new", pages.TransferNew)
		r.Post("/transactions/transfer", pages.TransferCreate)
		r.Post("/transactions/instapay-transfer", pages.InstapayTransferCreate)
		r.Get("/exchange/new", pages.ExchangeNew)
		r.Get("/transactions/quick-transfer", pages.QuickTransferForm)
		r.Get("/exchange/quick-form", pages.QuickExchangeForm)
		r.Post("/transactions/exchange-submit", pages.ExchangeCreate)
		r.Get("/people", pages.People)
		r.Post("/people/add", pages.PeopleAdd)
		r.Get("/people/{id}", pages.PersonDetail)
		r.Post("/people/{id}/loan", pages.PeopleLoan)
		r.Post("/people/{id}/repay", pages.PeopleRepay)
		r.Get("/recurring", pages.Recurring)
		r.Post("/recurring/add", pages.RecurringAdd)
		r.Post("/recurring/{id}/confirm", pages.RecurringConfirm)
		r.Post("/recurring/{id}/skip", pages.RecurringSkip)
		r.Delete("/recurring/{id}", pages.RecurringDelete)
		r.Post("/sync/transactions", pages.SyncTransactions)
		r.Get("/reports", pages.Reports)
		r.Get("/fawry-cashout", pages.FawryCashout)
		r.Post("/transactions/fawry-cashout", pages.FawryCashoutCreate)
		r.Get("/salary", pages.Salary)
		r.Post("/salary/step2", pages.SalaryStep2)
		r.Post("/salary/step3", pages.SalaryStep3)
		r.Post("/salary/confirm", pages.SalaryConfirm)
		r.Get("/investments", pages.Investments)
		r.Post("/investments/add", pages.InvestmentAdd)
		r.Post("/investments/{id}/update", pages.InvestmentUpdateValuation)
		r.Delete("/investments/{id}", pages.InvestmentDelete)
		r.Get("/installments", pages.Installments)
		r.Post("/installments/add", pages.InstallmentAdd)
		r.Post("/installments/{id}/pay", pages.InstallmentPay)
		r.Delete("/installments/{id}", pages.InstallmentDelete)
		r.Get("/batch-entry", pages.BatchEntry)
		r.Post("/transactions/batch", pages.BatchCreate)
		// TASK-062: Virtual funds routes
		r.Get("/virtual-funds", pages.VirtualFunds)
		r.Post("/virtual-funds/add", pages.VirtualFundAdd)
		r.Get("/virtual-funds/{id}", pages.VirtualFundDetail)
		r.Post("/virtual-funds/{id}/archive", pages.VirtualFundArchive)
		r.Post("/virtual-funds/{id}/allocate", pages.VirtualFundAllocate)
		// TASK-065: Budget routes
		r.Get("/budgets", pages.Budgets)
		r.Post("/budgets/add", pages.BudgetAdd)
		r.Post("/budgets/{id}/delete", pages.BudgetDelete)

		r.Get("/exchange-rates", pages.ExchangeRates)
		r.Get("/settings", pages.Settings)
		r.Post("/settings/pin", pages.ChangePin)
		r.Get("/export/transactions", pages.ExportTransactions)
		r.Get("/api/transactions/suggest-category", pages.SuggestCategory)

		// Push notification endpoints
		push := NewPushHandler(notificationSvc, os.Getenv("VAPID_PUBLIC_KEY"))
		r.Get("/api/push/vapid-key", push.VAPIDKey)
		r.Post("/api/push/subscribe", push.Subscribe)
		r.Get("/api/push/check", push.CheckNotifications)
	})

	return r
}
