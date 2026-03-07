// Package handler defines HTTP handlers and routes.
// This is like Laravel's routes/web.php + Controllers, or Django's urls.py + views.py.
package handler

import (
	"database/sql"
	"log"
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
		pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
		r.Get("/", pages.Home)
		return r
	}

	// -- Database-dependent routes --

	// Repos
	institutionRepo := repository.NewInstitutionRepo(db)
	accountRepo := repository.NewAccountRepo(db)
	categoryRepo := repository.NewCategoryRepo(db)
	txRepo := repository.NewTransactionRepo(db)

	personRepo := repository.NewPersonRepo(db)

	// Services
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
	reportsSvc := service.NewReportsService(db)
	recurringRepo := repository.NewRecurringRepo(db)
	recurringSvc := service.NewRecurringService(recurringRepo, txSvc)
	installmentRepo := repository.NewInstallmentRepo(db)
	installmentSvc := service.NewInstallmentService(installmentRepo, txSvc)
	notificationSvc := service.NewNotificationService(dashboardSvc, recurringSvc)
	exportSvc := service.NewExportService(txRepo)
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
		r.Route("/api/persons", NewPersonHandler(personSvc).Routes)

		// Page routes (HTML)
		pages := NewPageHandler(tmpl, institutionSvc, accountSvc, categorySvc, txSvc, dashboardSvc, personSvc, salarySvc, reportsSvc, recurringSvc, investmentSvc, installmentSvc, exportSvc, authSvc, exchangeRateRepo)
		r.Get("/", pages.Home)
		r.Get("/partials/recent-transactions", pages.RecentTransactions)
		r.Get("/partials/people-summary", pages.PeopleSummary)
		r.Get("/partials/building-fund", pages.BuildingFund)
		r.Get("/accounts", pages.Accounts)
		r.Get("/accounts/form", pages.AccountForm)
		r.Get("/accounts/list", pages.InstitutionList)
		r.Get("/accounts/{id}", pages.AccountDetail)
		r.Post("/accounts/{id}/dormant", pages.ToggleDormant)
		r.Post("/accounts/reorder", pages.ReorderAccounts)
		r.Post("/institutions/reorder", pages.ReorderInstitutions)
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
		r.Post("/transactions/transfer", pages.TransferCreate)
		r.Post("/transactions/instapay-transfer", pages.InstapayTransferCreate)
		r.Post("/transactions/exchange-submit", pages.ExchangeCreate)
		r.Get("/people", pages.People)
		r.Post("/people/add", pages.PeopleAdd)
		r.Post("/people/{id}/loan", pages.PeopleLoan)
		r.Post("/people/{id}/repay", pages.PeopleRepay)
		r.Get("/recurring", pages.Recurring)
		r.Post("/recurring/add", pages.RecurringAdd)
		r.Post("/recurring/{id}/confirm", pages.RecurringConfirm)
		r.Post("/recurring/{id}/skip", pages.RecurringSkip)
		r.Delete("/recurring/{id}", pages.RecurringDelete)
		r.Post("/sync/transactions", pages.SyncTransactions)
		r.Get("/reports", pages.Reports)
		r.Get("/building-fund", pages.BuildingFundPage)
		r.Post("/building-fund/add", pages.BuildingFundAdd)
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

		r.Get("/exchange-rates", pages.ExchangeRates)
		r.Get("/settings", pages.Settings)
		r.Post("/settings/pin", pages.ChangePin)
		r.Get("/export/transactions", pages.ExportTransactions)

		// Push notification endpoints
		push := NewPushHandler(notificationSvc, os.Getenv("VAPID_PUBLIC_KEY"))
		r.Get("/api/push/vapid-key", push.VAPIDKey)
		r.Post("/api/push/subscribe", push.Subscribe)
		r.Get("/api/push/check", push.CheckNotifications)
	})

	return r
}
