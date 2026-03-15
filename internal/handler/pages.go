// pages.go — HTML page handlers for the HTMX-powered web interface.
//
// This is the largest handler file (~2300 lines) because it serves ALL HTML pages
// and HTMX partials. Think of it as the combined web routes controller in Laravel
// or all the template views in Django.
//
// =============================================================================
// HTMX Pattern Guide for Laravel/Django Developers
// =============================================================================
//
// HTMX replaces traditional full-page form submissions and JavaScript SPAs with
// a simple approach: HTML attributes on elements trigger HTTP requests, and the
// server returns HTML fragments that replace parts of the page.
//
// Key HTMX attributes used in this app:
//
//   hx-get="/path"       — Makes a GET request when the element is triggered
//                          Like: fetch('/path').then(html => element.innerHTML = html)
//
//   hx-post="/path"      — Makes a POST request (form submission without page reload)
//                          Like Laravel Livewire or Django HTMX
//
//   hx-target="#element"  — Where to put the response HTML (CSS selector)
//                          Like jQuery's $(target).html(response)
//
//   hx-swap="innerHTML"   — How to insert the response: innerHTML, outerHTML, beforeend, etc.
//
//   hx-trigger="change"   — When to fire: click, change, submit, load, etc.
//
// Server-side HTMX patterns in this file:
//
//   1. Full page render: RenderPage(templates, w, "home", PageData{...})
//      Returns a complete HTML page (base layout + content).
//      Like: return view('home', $data) in Laravel.
//
//   2. Partial render: tmpl.ExecuteTemplate(w, "transaction-row", data)
//      Returns just an HTML fragment (no layout wrapper).
//      HTMX swaps this fragment into the existing page.
//      Like: return view('partials.transaction-row', $data) in Laravel.
//
//   3. HX-Redirect header: w.Header().Set("HX-Redirect", "/investments")
//      Tells HTMX to do a full-page redirect (client-side navigation).
//      Like: return redirect('/investments') but via an HTMX response header.
//
//   4. Inline HTML responses: w.Write([]byte(`<div class="bg-green-50">...</div>`))
//      Returns small HTML snippets directly (success/error messages).
//      HTMX swaps these into a target element for toast-style feedback.
//
// Form handling:
//   Page handlers use r.ParseForm() + r.FormValue("field") for form data.
//   This is different from API handlers which use json.NewDecoder(r.Body).Decode().
//   Forms use Content-Type: application/x-www-form-urlencoded (standard HTML forms).
//
// See: https://htmx.org/docs/ (HTMX documentation)
// See: https://htmx.org/reference/#headers (HX-Redirect and other response headers)
// =============================================================================
package handler

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/jackc/pgx/v5/pgconn"

	authmw "github.com/shahwan42/clearmoney/internal/middleware"
	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/service"
	"github.com/shahwan42/clearmoney/internal/timeutil"
)

// parseFloat is a convenience wrapper around strconv.ParseFloat.
// Used throughout this file to convert form field strings to float64.
// In PHP, you'd use floatval($str). In Python, float(str).
func parseFloat(s string) (float64, error) {
	return strconv.ParseFloat(s, 64)
}

// parseDate parses a "YYYY-MM-DD" date string as midnight in the user's timezone,
// returning UTC. This ensures date inputs from forms are interpreted correctly.
// In PHP: DateTime::createFromFormat('Y-m-d', $str, new DateTimeZone('Africa/Cairo'))
// In Python: datetime.strptime(str, '%Y-%m-%d').replace(tzinfo=user_tz)
func (h *PageHandler) parseDate(s string) (time.Time, error) {
	return timeutil.ParseDateInTZ(s, h.loc)
}

// htmxRedirect sends HX-Redirect for HTMX requests or http.Redirect for standard POST forms.
// Like Laravel's redirect()->back() but aware of whether the request came from HTMX or a browser form.
func htmxRedirect(w http.ResponseWriter, r *http.Request, url string) {
	if r.Header.Get("HX-Request") == "true" {
		w.Header().Set("HX-Redirect", url)
		w.WriteHeader(http.StatusOK)
		return
	}
	http.Redirect(w, r, url, http.StatusSeeOther)
}

// HTMXResultData holds data for the htmx-result partial template.
type HTMXResultData struct {
	Type    string // "success", "error", or "info"
	Message string
	Detail  string // optional secondary text
}

// renderHTMXResult renders the htmx-result template partial for HTMX responses.
func (h *PageHandler) renderHTMXResult(w http.ResponseWriter, resultType, message, detail string) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	for _, tmpl := range h.templates {
		if err := tmpl.ExecuteTemplate(w, "htmx-result", HTMXResultData{
			Type:    resultType,
			Message: message,
			Detail:  detail,
		}); err == nil {
			return
		}
	}
	// Fallback if template not found
	fmt.Fprintf(w, `<div class="p-3 rounded-lg text-sm">%s</div>`, message)
}

// =============================================================================
// View Model Structs — Data shapes for template rendering
// =============================================================================
//
// These structs are "View Models" (or "Data Transfer Objects"). They combine data
// from multiple sources into a shape that's convenient for the template.
//
// In Laravel: these would be the arrays you pass to view('page', $data).
// In Django: these would be the context dictionaries for render(request, 'page.html', context).
//
// In Go templates, these become the "dot" (.) value. Template accesses them with:
//   {{.Institution.Name}}   — struct field access
//   {{range .Accounts}}     — iteration over a slice
//   {{if .HasMore}}         — conditional rendering

// InstitutionWithAccounts groups an institution with its accounts for template rendering.
// This is like a ViewModel — it combines data from multiple sources
// into a shape that's convenient for the template.
type InstitutionWithAccounts struct {
	Institution models.Institution
	Accounts    []models.Account
}

// AccountFormData holds the data needed to render the account creation form.
type AccountFormData struct {
	InstitutionID   string
	InstitutionName string
	Error           string
}

// AccountEditFormData holds data for the account edit bottom sheet form.
type AccountEditFormData struct {
	Account models.Account
}

// TransactionFormData holds data for the transaction entry form dropdowns.
type TransactionFormData struct {
	Accounts           []models.Account
	ExpenseCategories  []models.Category
	IncomeCategories   []models.Category
	Today              time.Time
	// Pre-fill fields (for transaction duplication)
	Prefill         *models.Transaction
	VirtualAccounts []models.VirtualAccount // Optional virtual account allocation
}

// TransactionListData holds data for the transaction list page and partial.
// TransactionDisplay wraps a Transaction with display-enriched fields.
// Embeds models.Transaction so all existing template field accesses work unchanged.
type TransactionDisplay struct {
	models.Transaction
	AccountName     string  // joined from accounts table
	RunningBalance  float64 // balance after this transaction was applied
	ShowAccountName bool    // false on account detail page (account is in header)
}

// toTransactionDisplay converts repository display rows to handler-level display structs.
func toTransactionDisplay(rows []repository.TransactionDisplayRow, showAccountName bool) []TransactionDisplay {
	result := make([]TransactionDisplay, len(rows))
	for i, r := range rows {
		result[i] = TransactionDisplay{
			Transaction:     r.Transaction,
			AccountName:     r.AccountName,
			RunningBalance:  r.RunningBalance,
			ShowAccountName: showAccountName,
		}
	}
	return result
}

type TransactionListData struct {
	Transactions []TransactionDisplay
	Accounts     []models.Account
	Categories   []models.Category
	HasMore      bool
	NextOffset   int
	// Current filter values (for "load more" links)
	AccountID  string
	CategoryID string
	Type       string
	DateFrom   string
	DateTo     string
	Search     string
}

// TransactionEditData holds data for the inline edit form.
type TransactionEditData struct {
	Transaction              models.Transaction
	Categories               []models.Category
	SelectedCategoryID       string
	VirtualAccounts          []models.VirtualAccount
	SelectedVirtualAccountID string
}

// TransactionSuccessData is shown after a successful transaction creation.
type TransactionSuccessData struct {
	Transaction models.Transaction
	NewBalance  float64
	Currency    string
}

// InstitutionDeleteData holds data for the institution delete confirmation sheet.
type InstitutionDeleteData struct {
	InstitutionID   string
	InstitutionName string
	AccountCount    int
}

// InstitutionCreateData holds data for the institution create form in the bottom sheet.
type InstitutionCreateData struct {
	Error string
}

// InstitutionEditData holds data for the inline institution edit form in the bottom sheet.
type InstitutionEditData struct {
	Institution models.Institution
	Error       string
}

// QuickEntryData holds the quick-entry form data with smart defaults.
type QuickEntryData struct {
	TransactionFormData
	LastAccountID  string
	AutoCategoryID string
}

// AccountDetailData holds data for the account detail page.
type AccountDetailData struct {
	Account             models.Account
	InstitutionName     string
	BillingCycle        *service.BillingCycleInfo
	TransactionListData TransactionListData
	// TASK-059: 30-day balance sparkline data
	BalanceHistory []float64
	// TASK-068: Account health constraints
	HealthConfig *models.AccountHealthConfig
	// TASK-073: Credit card utilization percentage
	Utilization float64
	// TASK-076: Credit card utilization history (monthly %)
	UtilizationHistory []float64
	// Linked virtual accounts for this bank account
	VirtualAccounts []models.VirtualAccount
}

// PersonCardData wraps a person with accounts for the card template.
type PersonCardData struct {
	Person   models.Person
	Accounts []models.Account
}

// PeoplePageData holds data for the people page.
type PeoplePageData struct {
	Persons  []PersonCardData
	Accounts []models.Account
}

// RecurringRuleView is a display-friendly view of a recurring rule.
type RecurringRuleView struct {
	ID          string
	Note        string
	Amount      string
	Frequency   string
	NextDueDate time.Time
	AutoConfirm bool
}

// RecurringPageData holds data for the recurring rules page.
type RecurringPageData struct {
	Rules        []RecurringRuleView
	PendingRules []RecurringRuleView
	Accounts     []models.Account
	Categories   []models.Category
	Today        time.Time
}

// SalaryStepData holds data passed between salary wizard steps.
type SalaryStepData struct {
	Accounts     []models.Account
	EGPAccounts  []models.Account
	SalaryUSD    float64
	ExchangeRate float64
	SalaryEGP    float64
	USDAccountID string
	EGPAccountID string
	Date         string
	Today        time.Time
}

// SalarySuccessData holds data for the salary success confirmation.
type SalarySuccessData struct {
	SalaryUSD    float64
	ExchangeRate float64
	SalaryEGP    float64
	AllocCount   int
}

// =============================================================================
// PageHandler — The main HTML page controller
// =============================================================================
//
// PageHandler serves full HTML pages (as opposed to JSON API endpoints).
// Think of it like Laravel's web routes vs API routes — same data, different format.
//
// This is the largest struct in the app with 15+ service dependencies.
// In Laravel, this would be like a controller with many injected services.
// In Django, this would be like a view class with many service attributes.
//
// Dependency injection pattern:
//   - Required dependencies: passed via constructor (NewPageHandler)
//   - Optional dependencies: added via setter methods (SetSnapshotService, etc.)
//   - The setter pattern is used for dependencies added in later development phases
//     to avoid changing the constructor signature (which would break all callers).
//
// Nil-safety: All methods check if their service is nil before calling it.
// This allows the handler to work in "no-DB mode" for template-only rendering.
type PageHandler struct {
	templates      TemplateMap
	loc            *time.Location // User timezone for date parsing and display
	institutionSvc *service.InstitutionService
	accountSvc     *service.AccountService
	categorySvc    *service.CategoryService
	txSvc          *service.TransactionService
	dashboardSvc   *service.DashboardService
	personSvc      *service.PersonService
	salarySvc      *service.SalaryService
	reportsSvc     *service.ReportsService
	recurringSvc   *service.RecurringService
	investmentSvc   *service.InvestmentService
	installmentSvc  *service.InstallmentService
	exportSvc        *service.ExportService
	authSvc          *service.AuthService
	exchangeRateRepo *repository.ExchangeRateRepo
	snapshotSvc      *service.SnapshotService    // TASK-059: account balance sparklines
	virtualAccountSvc *service.VirtualAccountService // TASK-062: virtual accounts CRUD
	budgetSvc        *service.BudgetService      // TASK-065: budget management
	healthSvc        *service.AccountHealthService // TASK-068: account health
}

// NewPageHandler creates the page handler with all required service dependencies.
// This long parameter list is a trade-off: verbose but explicit.
// In Laravel, you'd use constructor injection with the Service Container:
//   public function __construct(InstitutionService $inst, AccountService $acc, ...)
// In Django, services might be instantiated in the view or injected via settings.
// In Go, there's no DI container — you wire dependencies manually in router.go.
func NewPageHandler(templates TemplateMap, institutionSvc *service.InstitutionService, accountSvc *service.AccountService, categorySvc *service.CategoryService, txSvc *service.TransactionService, dashboardSvc *service.DashboardService, personSvc *service.PersonService, salarySvc *service.SalaryService, reportsSvc *service.ReportsService, recurringSvc *service.RecurringService, investmentSvc *service.InvestmentService, installmentSvc *service.InstallmentService, exportSvc *service.ExportService, authSvc *service.AuthService, exchangeRateRepo *repository.ExchangeRateRepo) *PageHandler {
	return &PageHandler{
		templates:       templates,
		institutionSvc:  institutionSvc,
		accountSvc:      accountSvc,
		categorySvc:     categorySvc,
		txSvc:           txSvc,
		dashboardSvc:    dashboardSvc,
		personSvc:       personSvc,
		salarySvc:       salarySvc,
		reportsSvc:      reportsSvc,
		recurringSvc:    recurringSvc,
		investmentSvc:   investmentSvc,
		installmentSvc:  installmentSvc,
		exportSvc:        exportSvc,
		authSvc:          authSvc,
		exchangeRateRepo: exchangeRateRepo,
	}
}

// SetTimezone sets the user's timezone for date parsing and display.
func (h *PageHandler) SetTimezone(loc *time.Location) {
	h.loc = loc
}

// SetSnapshotService sets the snapshot service for account balance sparklines (TASK-059).
func (h *PageHandler) SetSnapshotService(svc *service.SnapshotService) {
	h.snapshotSvc = svc
}

// SetVirtualAccountService sets the virtual account service for CRUD operations (TASK-062).
func (h *PageHandler) SetVirtualAccountService(svc *service.VirtualAccountService) {
	h.virtualAccountSvc = svc
}

// SetBudgetService sets the budget service for budget management (TASK-065).
func (h *PageHandler) SetBudgetService(svc *service.BudgetService) {
	h.budgetSvc = svc
}

// SetAccountHealthService sets the health service for account constraints (TASK-068).
func (h *PageHandler) SetAccountHealthService(svc *service.AccountHealthService) {
	h.healthSvc = svc
}

// =============================================================================
// Dashboard / Home
// =============================================================================

// Home renders the dashboard page.
// GET /
//
// This is the main landing page after login. It aggregates data from 10+ sources
// (accounts, transactions, budgets, virtual accounts, health, etc.) via DashboardService.
//
// Nil-safety: if dashboardSvc is nil (no-DB mode), renders an empty-state dashboard.
// Like Laravel: return view('home', ['data' => $this->dashboardService?->getDashboard()])
func (h *PageHandler) Home(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "dashboard")
	var data any
	if h.dashboardSvc != nil {
		dashData, err := h.dashboardSvc.GetDashboard(r.Context())
		if err != nil {
			authmw.Log(r.Context()).Error("failed to load dashboard", "error", err)
		} else {
			data = dashData
		}
	}
	RenderPage(h.templates, w, "home", PageData{ActiveTab: "home", Data: data})
}

// =============================================================================
// Accounts Section
// =============================================================================

// Accounts renders the accounts management page.
// GET /accounts
//
// Groups accounts by institution (bank/fintech) for display.
// The template iterates over []InstitutionWithAccounts to render institution cards.
func (h *PageHandler) Accounts(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "accounts")
	institutions, err := h.institutionSvc.GetAll(r.Context())
	if err != nil {
		authmw.Log(r.Context()).Error("failed to load institutions", "error", err)
		http.Error(w, "failed to load institutions", http.StatusInternalServerError)
		return
	}

	// Build institution-with-accounts list for the template
	var data []InstitutionWithAccounts
	for _, inst := range institutions {
		accounts, err := h.accountSvc.GetByInstitution(r.Context(), inst.ID)
		if err != nil {
			accounts = []models.Account{}
		}
		data = append(data, InstitutionWithAccounts{
			Institution: inst,
			Accounts:    accounts,
		})
	}

	RenderPage(h.templates, w, "accounts", PageData{ActiveTab: "accounts", Data: data})
}

// AccountForm renders the account creation form for a specific institution.
// GET /accounts/form?institution_id=xxx — called by HTMX.
//
// This is an HTMX partial endpoint: it returns just the form HTML fragment,
// not a full page. HTMX swaps this into the page when the user clicks
// "Add Account" under an institution.
//
// Pattern: tmpl.ExecuteTemplate(w, "account-form", data) renders a single
// named template block, not the full page layout. This is how Go serves
// HTML partials for HTMX — like rendering a Blade @include without @extends.
func (h *PageHandler) AccountForm(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "account-form")
	institutionID := r.URL.Query().Get("institution_id")
	if institutionID == "" {
		http.Error(w, "institution_id required", http.StatusBadRequest)
		return
	}

	instName := ""
	inst, err := h.institutionSvc.GetByID(r.Context(), institutionID)
	if err == nil {
		instName = inst.Name
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["accounts"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "account-form", AccountFormData{
		InstitutionID:   institutionID,
		InstitutionName: instName,
	})
}

// AccountEditForm renders the account edit form partial for the bottom sheet.
// GET /accounts/{id}/edit-form — called by HTMX when the edit sheet opens.
func (h *PageHandler) AccountEditForm(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "account-edit-form")
	id := chi.URLParam(r, "id")
	acc, err := h.accountSvc.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, "account not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["account-detail"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "account-edit-form", AccountEditFormData{Account: acc})
}

// AccountUpdate handles the form submission for editing an account.
// POST /accounts/{id}/edit — called by HTMX from the edit bottom sheet.
func (h *PageHandler) AccountUpdate(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form", http.StatusBadRequest)
		return
	}

	// Fetch existing account to preserve non-editable fields (balance, metadata, etc.)
	acc, err := h.accountSvc.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, "account not found", http.StatusNotFound)
		return
	}

	// Override editable fields from form
	acc.Name = r.FormValue("name")
	acc.Type = models.AccountType(r.FormValue("type"))
	acc.Currency = models.Currency(r.FormValue("currency"))

	// Parse credit limit (nullable)
	acc.CreditLimit = nil
	if v := r.FormValue("credit_limit"); v != "" {
		if f, err := parseFloat(v); err == nil {
			acc.CreditLimit = &f
		}
	}

	if _, err := h.accountSvc.Update(r.Context(), acc); err != nil {
		authmw.Log(r.Context()).Warn("account update failed", "error", err)
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusUnprocessableEntity)
		fmt.Fprintf(w, `<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm mb-3">%s</div>`, err.Error())
		return
	}

	htmxRedirect(w, r, "/accounts/"+id)
}

// =============================================================================
// Transactions Section
// =============================================================================

// TransactionNew renders the transaction entry form.
// GET /transactions/new
// Supports ?dup=<id> to pre-fill from an existing transaction (duplication).
//
// The ?dup parameter enables "duplicate transaction" — when a user wants to
// quickly re-enter a similar transaction, the form pre-fills all fields from
// an existing transaction. This saves time for repetitive expenses.
func (h *PageHandler) TransactionNew(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "transaction-new")
	accounts, err := h.accountSvc.GetAll(r.Context())
	if err != nil {
		accounts = []models.Account{}
	}
	expenseCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense)
	incomeCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeIncome)

	var virtualAccounts []models.VirtualAccount
	if h.virtualAccountSvc != nil {
		virtualAccounts, _ = h.virtualAccountSvc.GetAll(r.Context())
	}

	data := TransactionFormData{
		Accounts:          accounts,
		ExpenseCategories: expenseCategories,
		IncomeCategories:  incomeCategories,
		Today:             timeutil.Now(),
		VirtualAccounts:   virtualAccounts,
	}

	// If ?dup=<id> is provided, pre-fill from that transaction
	if dupID := r.URL.Query().Get("dup"); dupID != "" {
		if tx, err := h.txSvc.GetByID(r.Context(), dupID); err == nil {
			data.Prefill = &tx
		}
	}

	RenderPage(h.templates, w, "transaction-new", PageData{
		ActiveTab: "transactions",
		Data:      data,
	})
}

// TransactionCreate handles the HTMX form submission for creating a transaction.
// POST /transactions — returns success partial or error HTML.
//
// This is an HTMX form handler. Instead of redirecting after form submission
// (like a traditional web app), it returns an HTML fragment:
//   - Success: renders "transaction-success" partial with the new balance
//   - Error: returns a red error div that HTMX swaps into the form area
//
// HTMX handles this transparently — the form's hx-post attribute sends the form
// data as a POST request, and hx-target specifies where to put the response HTML.
//
// Form parsing in Go:
//   r.ParseForm() reads the URL-encoded form body into r.Form (a map).
//   r.FormValue("amount") gets a single field value.
//   This is like Laravel's $request->input('amount') or Django's request.POST['amount'].
func (h *PageHandler) TransactionCreate(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	tx := models.Transaction{
		Type:      models.TransactionType(r.FormValue("type")),
		Amount:    amount,
		Currency:  models.Currency(r.FormValue("currency")),
		AccountID: r.FormValue("account_id"),
	}

	// Optional fields
	if catID := r.FormValue("category_id"); catID != "" {
		tx.CategoryID = &catID
	}
	if note := r.FormValue("note"); note != "" {
		tx.Note = &note
	}
	if dateStr := r.FormValue("date"); dateStr != "" {
		if parsed, err := h.parseDate(dateStr); err == nil {
			tx.Date = parsed
		}
	}

	created, newBalance, err := h.txSvc.Create(r.Context(), tx)
	if err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	// Allocate to virtual account if selected (validate account linkage)
	if vaID := r.FormValue("virtual_account_id"); vaID != "" && h.virtualAccountSvc != nil {
		if va, err := h.virtualAccountSvc.GetByID(r.Context(), vaID); err == nil {
			if va.AccountID == nil || *va.AccountID == created.AccountID {
				allocAmount := created.Amount
				if created.Type == models.TransactionTypeExpense {
					allocAmount = -created.Amount
				}
				if err := h.virtualAccountSvc.Allocate(r.Context(), created.ID, vaID, allocAmount); err != nil {
					authmw.Log(r.Context()).Warn("virtual account allocation failed",
						"transaction_id", created.ID, "virtual_account_id", vaID, "error", err)
				}
			} else {
				authmw.Log(r.Context()).Warn("virtual account not linked to transaction account",
					"transaction_id", created.ID, "virtual_account_id", vaID,
					"va_account_id", *va.AccountID, "tx_account_id", created.AccountID)
			}
		}
	}

	// Determine currency label
	cur := "EGP"
	if tx.Currency == models.CurrencyUSD {
		cur = "USD"
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["transaction-new"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "transaction-success", TransactionSuccessData{
		Transaction: created,
		NewBalance:  newBalance,
		Currency:    cur,
	})
}

// Transactions renders the full transaction list page with filters.
// GET /transactions
//
// Supports query parameter filters: account_id, category_id, type, date_from,
// date_to, search, offset. HTMX uses these filters to update the list
// without a full page reload — filter dropdowns trigger hx-get with query params.
func (h *PageHandler) Transactions(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "transactions")
	filter := h.parseTransactionFilter(r)

	rows, _ := h.txSvc.GetFilteredEnriched(r.Context(), filter)
	accounts, _ := h.accountSvc.GetAll(r.Context())
	categories, _ := h.categorySvc.GetAll(r.Context())

	data := TransactionListData{
		Transactions: toTransactionDisplay(rows, true),
		Accounts:     accounts,
		Categories:   categories,
		HasMore:      len(rows) >= filter.Limit,
		NextOffset:   filter.Offset + filter.Limit,
		AccountID:    filter.AccountID,
		CategoryID:   filter.CategoryID,
		Type:         filter.Type,
		DateFrom:     r.URL.Query().Get("date_from"),
		DateTo:       r.URL.Query().Get("date_to"),
		Search:       filter.Search,
	}

	RenderPage(h.templates, w, "transactions", PageData{ActiveTab: "transactions", Data: data})
}

// TransactionList renders just the transaction list partial (for HTMX filter updates).
// GET /transactions/list
//
// This is the HTMX partial companion to Transactions(). When the user changes
// a filter dropdown, HTMX calls this endpoint and swaps just the list content
// — no full page reload. The template renders only the "transaction-list" block.
//
// This pattern is fundamental to HTMX: full page = RenderPage(), partial = ExecuteTemplate().
func (h *PageHandler) TransactionList(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "transaction-list")
	filter := h.parseTransactionFilter(r)
	rows, _ := h.txSvc.GetFilteredEnriched(r.Context(), filter)

	data := TransactionListData{
		Transactions: toTransactionDisplay(rows, true),
		HasMore:      len(rows) >= filter.Limit,
		NextOffset:   filter.Offset + filter.Limit,
		AccountID:    filter.AccountID,
		CategoryID:   filter.CategoryID,
		Type:         filter.Type,
		DateFrom:     r.URL.Query().Get("date_from"),
		DateTo:       r.URL.Query().Get("date_to"),
		Search:       filter.Search,
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["transactions"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "transaction-list", data)
}

// parseTransactionFilter extracts filter parameters from query string.
func (h *PageHandler) parseTransactionFilter(r *http.Request) repository.TransactionFilter {
	q := r.URL.Query()
	f := repository.TransactionFilter{
		AccountID:  q.Get("account_id"),
		CategoryID: q.Get("category_id"),
		Type:       q.Get("type"),
		Search:     q.Get("search"),
		Limit:      50,
	}

	if v := q.Get("offset"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			f.Offset = n
		}
	}
	if v := q.Get("date_from"); v != "" {
		if t, err := h.parseDate(v); err == nil {
			f.DateFrom = &t
		}
	}
	if v := q.Get("date_to"); v != "" {
		if t, err := h.parseDate(v); err == nil {
			f.DateTo = &t
		}
	}

	return f
}

// TransferNew renders the transfer form page.
// GET /transfers/new
func (h *PageHandler) TransferNew(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "transfer-new")
	accounts, _ := h.accountSvc.GetAll(r.Context())
	RenderPage(h.templates, w, "transfer", PageData{
		ActiveTab: "transactions",
		Data: TransactionFormData{
			Accounts: accounts,
			Today:    timeutil.Now(),
		},
	})
}

// ExchangeNew renders the currency exchange form page.
// GET /exchange/new
func (h *PageHandler) ExchangeNew(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "exchange-new")
	accounts, _ := h.accountSvc.GetAll(r.Context())
	RenderPage(h.templates, w, "exchange", PageData{
		ActiveTab: "transactions",
		Data: TransactionFormData{
			Accounts: accounts,
			Today:    timeutil.Now(),
		},
	})
}

// TransferCreate handles the transfer form submission.
// POST /transactions/transfer — returns success or error partial.
func (h *PageHandler) TransferCreate(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	sourceID := r.FormValue("source_account_id")
	destID := r.FormValue("dest_account_id")
	currency := models.Currency(r.FormValue("currency"))

	var note *string
	if n := r.FormValue("note"); n != "" {
		note = &n
	}

	var date time.Time
	if d := r.FormValue("date"); d != "" {
		date, _ = h.parseDate(d)
	}

	// If currency not provided, look it up from the source account
	if currency == "" {
		if acc, err := h.accountSvc.GetByID(r.Context(), sourceID); err == nil {
			currency = acc.Currency
		}
	}

	_, _, err := h.txSvc.CreateTransfer(r.Context(), sourceID, destID, amount, currency, note, date)
	if err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(`<div class="bg-green-50 text-green-700 p-3 rounded-lg text-sm">Transfer completed successfully!</div>`))
}

// InstapayTransferCreate handles an InstaPay transfer with auto-calculated fee.
// POST /transactions/instapay-transfer
func (h *PageHandler) InstapayTransferCreate(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	sourceID := r.FormValue("source_account_id")
	destID := r.FormValue("dest_account_id")
	currency := models.Currency(r.FormValue("currency"))

	var note *string
	if n := r.FormValue("note"); n != "" {
		note = &n
	}

	var date time.Time
	if d := r.FormValue("date"); d != "" {
		date, _ = h.parseDate(d)
	}

	// If currency not provided, look it up from source account
	if currency == "" {
		if acc, err := h.accountSvc.GetByID(r.Context(), sourceID); err == nil {
			currency = acc.Currency
		}
	}

	// Look up "Fees & Charges" category ID
	feesCatID := ""
	if cats, err := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense); err == nil {
		for _, c := range cats {
			if c.Name == "Fees & Charges" {
				feesCatID = c.ID
				break
			}
		}
	}

	_, _, fee, err := h.txSvc.CreateInstapayTransfer(r.Context(), sourceID, destID, amount, currency, note, date, feesCatID)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		h.renderHTMXResult(w, "error", err.Error(), "")
		return
	}

	h.renderHTMXResult(w, "success", fmt.Sprintf("InstaPay transfer completed! Fee: EGP %.2f", fee), "")
}

// ExchangeCreate handles the exchange form submission.
// POST /transactions/exchange-submit — returns success or error partial.
func (h *PageHandler) ExchangeCreate(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	params := service.ExchangeParams{
		SourceAccountID: r.FormValue("source_account_id"),
		DestAccountID:   r.FormValue("dest_account_id"),
		Note:            nil,
	}

	if v := r.FormValue("amount"); v != "" {
		f, _ := parseFloat(v)
		params.Amount = &f
	}
	if v := r.FormValue("rate"); v != "" {
		f, _ := parseFloat(v)
		params.Rate = &f
	}
	if v := r.FormValue("counter_amount"); v != "" {
		f, _ := parseFloat(v)
		params.CounterAmount = &f
	}
	if v := r.FormValue("note"); v != "" {
		params.Note = &v
	}
	if v := r.FormValue("date"); v != "" {
		if t, err := h.parseDate(v); err == nil {
			params.Date = t
		}
	}

	_, _, err := h.txSvc.CreateExchange(r.Context(), params)
	if err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if r.FormValue("from_sheet") == "1" {
		w.Write([]byte(`<div class="bg-teal-50 dark:bg-teal-900/30 border border-teal-200 dark:border-teal-700 rounded-xl p-4 text-center space-y-2">
			<p class="text-teal-800 dark:text-teal-200 font-semibold text-sm">Exchange completed!</p>
			<button type="button" onclick="closeQuickEntry()"
				class="mt-2 px-4 py-1.5 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700">
				Done
			</button>
		</div>
		<div id="recent-transactions" hx-get="/partials/recent-transactions" hx-trigger="load" hx-swap-oob="true"></div>`))
	} else {
		w.Write([]byte(`<div class="bg-green-50 text-green-700 p-3 rounded-lg text-sm">Exchange completed successfully!</div>`))
	}
}

// TransactionEditForm renders the inline edit form for a transaction.
// GET /transactions/edit/{id} — called by HTMX.
//
// HTMX inline editing pattern:
//   1. User clicks "edit" on a transaction row
//   2. HTMX sends GET /transactions/edit/{id}
//   3. Server returns an edit form HTML fragment
//   4. HTMX swaps the read-only row with the edit form (hx-swap="outerHTML")
//   5. User submits the form (PUT /transactions/{id})
//   6. Server returns the updated read-only row
//   7. HTMX swaps the form back to the updated row
//
// This is like inline editing in a spreadsheet — no modal, no page navigation.
func (h *PageHandler) TransactionEditForm(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "transaction-edit-form")
	id := chi.URLParam(r, "id")
	tx, err := h.txSvc.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, "transaction not found", http.StatusNotFound)
		return
	}

	categories, _ := h.categorySvc.GetAll(r.Context())

	selectedCatID := ""
	if tx.CategoryID != nil {
		selectedCatID = *tx.CategoryID
	}

	// Fetch virtual accounts and current allocation for the transaction
	var virtualAccounts []models.VirtualAccount
	var selectedVAID string
	if h.virtualAccountSvc != nil {
		virtualAccounts, _ = h.virtualAccountSvc.GetAll(r.Context())
		if allocs, err := h.virtualAccountSvc.GetTransactionAllocations(r.Context(), id); err == nil && len(allocs) > 0 {
			selectedVAID = allocs[0].VirtualAccountID
		}
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["transactions"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "transaction-edit-form", TransactionEditData{
		Transaction:              tx,
		Categories:               categories,
		SelectedCategoryID:       selectedCatID,
		VirtualAccounts:          virtualAccounts,
		SelectedVirtualAccountID: selectedVAID,
	})
}

// TransactionUpdate handles the inline edit form submission.
// PUT /transactions/{id} — called by HTMX, returns updated row partial.
func (h *PageHandler) TransactionUpdate(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	tx := models.Transaction{
		ID:        id,
		Type:      models.TransactionType(r.FormValue("type")),
		Amount:    amount,
		Currency:  models.Currency(r.FormValue("currency")),
		AccountID: r.FormValue("account_id"),
	}
	if catID := r.FormValue("category_id"); catID != "" {
		tx.CategoryID = &catID
	}
	if note := r.FormValue("note"); note != "" {
		tx.Note = &note
	}
	if dateStr := r.FormValue("date"); dateStr != "" {
		if parsed, err := h.parseDate(dateStr); err == nil {
			tx.Date = parsed
		}
	}

	updated, _, err := h.txSvc.Update(r.Context(), tx)
	if err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	// Update virtual account allocation if changed (validate account linkage)
	newVAID := r.FormValue("virtual_account_id")
	if h.virtualAccountSvc != nil {
		// Find current allocation
		var oldVAID string
		if allocs, err := h.virtualAccountSvc.GetTransactionAllocations(r.Context(), id); err == nil && len(allocs) > 0 {
			oldVAID = allocs[0].VirtualAccountID
		}

		if oldVAID != newVAID {
			// Deallocate from old virtual account
			if oldVAID != "" {
				if err := h.virtualAccountSvc.Deallocate(r.Context(), id, oldVAID); err != nil {
					authmw.Log(r.Context()).Warn("virtual account deallocation failed",
						"transaction_id", id, "virtual_account_id", oldVAID, "error", err)
				}
			}
			// Allocate to new virtual account (with account linkage validation)
			if newVAID != "" {
				if va, err := h.virtualAccountSvc.GetByID(r.Context(), newVAID); err == nil {
					if va.AccountID == nil || *va.AccountID == updated.AccountID {
						allocAmount := updated.Amount
						if updated.Type == models.TransactionTypeExpense {
							allocAmount = -updated.Amount
						}
						if err := h.virtualAccountSvc.Allocate(r.Context(), id, newVAID, allocAmount); err != nil {
							authmw.Log(r.Context()).Warn("virtual account allocation failed",
								"transaction_id", id, "virtual_account_id", newVAID, "error", err)
						}
					} else {
						authmw.Log(r.Context()).Warn("virtual account not linked to transaction account",
							"transaction_id", id, "virtual_account_id", newVAID)
					}
				}
			}
		}
	}

	// Re-fetch enriched data for proper display (account name, running balance)
	row, err := h.txSvc.GetByIDEnriched(r.Context(), updated.ID)
	if err != nil {
		// Fallback: render with basic data if enriched fetch fails
		row.Transaction = updated
	}
	display := TransactionDisplay{
		Transaction:     row.Transaction,
		AccountName:     row.AccountName,
		RunningBalance:  row.RunningBalance,
		ShowAccountName: true,
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["transactions"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "transaction-row", display)
}

// TransactionDelete handles transaction deletion from the UI.
// DELETE /transactions/{id} — called by HTMX, returns empty (row removed).
//
// HTMX delete pattern: returns empty 200 response. The template uses
// hx-swap="outerHTML" on the row, so an empty response removes the row from the DOM.
// The swipe-to-delete gesture (TASK-080) triggers this endpoint.
func (h *PageHandler) TransactionDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	// Deallocate from virtual accounts before deleting the transaction,
	// so the cached current_balance gets recalculated properly.
	if h.virtualAccountSvc != nil {
		if allocs, err := h.virtualAccountSvc.GetTransactionAllocations(r.Context(), id); err == nil {
			for _, a := range allocs {
				if err := h.virtualAccountSvc.Deallocate(r.Context(), id, a.VirtualAccountID); err != nil {
					authmw.Log(r.Context()).Warn("failed to deallocate virtual account",
						"transaction_id", id, "virtual_account_id", a.VirtualAccountID, "error", err)
				}
			}
		}
	}

	if err := h.txSvc.Delete(r.Context(), id); err != nil {
		authmw.Log(r.Context()).Error("failed to delete transaction", "id", id, "error", err)
		http.Error(w, "failed to delete", http.StatusInternalServerError)
		return
	}
	// Return empty content — HTMX will remove the row from the DOM
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
}

// TransactionRow renders a single transaction row partial.
// GET /transactions/row/{id} — used by HTMX to cancel edit (swap back to row).
func (h *PageHandler) TransactionRow(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	row, err := h.txSvc.GetByIDEnriched(r.Context(), id)
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}

	display := TransactionDisplay{
		Transaction:     row.Transaction,
		AccountName:     row.AccountName,
		RunningBalance:  row.RunningBalance,
		ShowAccountName: true,
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["transactions"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "transaction-row", display)
}

// =============================================================================
// People Section — Loan/debt tracking between the user and other people
// =============================================================================

// People renders the people ledger page.
// GET /people
//
// Shows all people with their current debt status (owe you / you owe / settled).
// Each person card includes loan/repay forms powered by HTMX.
func (h *PageHandler) People(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "people")
	persons, _ := h.personSvc.GetAll(r.Context())
	accounts, _ := h.accountSvc.GetAll(r.Context())

	var cards []PersonCardData
	for _, p := range persons {
		cards = append(cards, PersonCardData{Person: p, Accounts: accounts})
	}

	RenderPage(h.templates, w, "people", PageData{
		ActiveTab: "people",
		Data:      PeoplePageData{Persons: cards, Accounts: accounts},
	})
}

// PeopleAdd adds a new person via form submission.
// POST /people/add — returns updated people list partial.
func (h *PageHandler) PeopleAdd(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	name := r.FormValue("name")
	if name == "" {
		http.Error(w, "name is required", http.StatusBadRequest)
		return
	}

	_, err := h.personSvc.Create(r.Context(), models.Person{Name: name})
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	h.renderPeopleList(w, r)
}

// PeopleLoan records a loan from the people page.
// POST /people/{id}/loan
func (h *PageHandler) PeopleLoan(w http.ResponseWriter, r *http.Request) {
	personID := chi.URLParam(r, "id")
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	accountID := r.FormValue("account_id")
	loanType := models.TransactionType(r.FormValue("loan_type"))

	// Get currency from account
	currency := models.CurrencyEGP
	if acc, err := h.accountSvc.GetByID(r.Context(), accountID); err == nil {
		currency = acc.Currency
	}

	var note *string
	if n := r.FormValue("note"); n != "" {
		note = &n
	}

	_, err := h.personSvc.RecordLoan(r.Context(), personID, accountID, amount, currency, loanType, note, time.Time{})
	if err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	h.renderPeopleList(w, r)
}

// PeopleRepay records a loan repayment from the people page.
// POST /people/{id}/repay
func (h *PageHandler) PeopleRepay(w http.ResponseWriter, r *http.Request) {
	personID := chi.URLParam(r, "id")
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	accountID := r.FormValue("account_id")

	currency := models.CurrencyEGP
	if acc, err := h.accountSvc.GetByID(r.Context(), accountID); err == nil {
		currency = acc.Currency
	}

	var note *string
	if n := r.FormValue("note"); n != "" {
		note = &n
	}

	_, err := h.personSvc.RecordRepayment(r.Context(), personID, accountID, amount, currency, note, time.Time{})
	if err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	h.renderPeopleList(w, r)
}

// renderPeopleList renders the people list partial (used after add/loan/repay).
// This is a private helper (lowercase name) — shared by PeopleAdd, PeopleLoan,
// and PeopleRepay to re-render the people list after a mutation.
// HTMX receives this HTML and swaps it into the people list container.
func (h *PageHandler) renderPeopleList(w http.ResponseWriter, r *http.Request) {
	persons, _ := h.personSvc.GetAll(r.Context())
	accounts, _ := h.accountSvc.GetAll(r.Context())

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["people"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}

	if len(persons) == 0 {
		w.Write([]byte(`<div class="bg-white rounded-xl shadow-sm p-6 text-center"><p class="text-gray-400 text-sm">No people yet. Add someone above.</p></div>`))
		return
	}

	for _, p := range persons {
		tmpl.ExecuteTemplate(w, "person-card", PersonCardData{Person: p, Accounts: accounts})
	}
}

// =============================================================================
// Dashboard Partials — HTMX endpoints for refreshing dashboard sections
// =============================================================================

// RecentTransactions renders just the recent transactions partial.
// GET /partials/recent-transactions — used by HTMX to refresh the dashboard feed.
//
// Dashboard partials follow this pattern: the full Home() handler renders
// the entire dashboard, but individual sections can be refreshed independently
// via these partial endpoints. HTMX loads them with hx-get on page load
// or after a mutation (e.g., after creating a quick-entry transaction).
func (h *PageHandler) RecentTransactions(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "recent-transactions")
	rows, _ := h.txSvc.GetRecentEnriched(r.Context(), 15)

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["home"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "recent-transactions", toTransactionDisplay(rows, true))
}

// PersonDetailData holds data for the person detail page (TASK-070).
// Shows full loan/repayment history, payoff progress, and projected payoff date.
type PersonDetailData struct {
	Summary  service.DebtSummary
	Accounts []models.Account
}

// PersonDetail renders the person detail page with debt tracking.
// GET /people/{id}
func (h *PageHandler) PersonDetail(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "person-detail")
	id := chi.URLParam(r, "id")

	summary, err := h.personSvc.GetDebtSummary(r.Context(), id)
	if err != nil {
		http.Error(w, "person not found", http.StatusNotFound)
		return
	}

	accounts, _ := h.accountSvc.GetAll(r.Context())

	RenderPage(h.templates, w, "person-detail", PageData{
		ActiveTab: "people",
		Data:      PersonDetailData{Summary: summary, Accounts: accounts},
	})
}

// AccountDetail renders the account detail page with transaction history.
// GET /accounts/{id}
//
// This is the most data-rich page — it aggregates:
//   - Account info (name, type, balance)
//   - Institution name
//   - Transaction history (filtered to this account)
//   - Balance sparkline (30-day history from snapshots)
//   - Credit card billing cycle info
//   - Credit card utilization percentage and history
//   - Account health constraints (min balance, min deposit)
func (h *PageHandler) AccountDetail(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "account-detail")
	id := chi.URLParam(r, "id")

	acc, err := h.accountSvc.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, "account not found", http.StatusNotFound)
		return
	}

	// Get institution name
	instName := ""
	if inst, err := h.institutionSvc.GetByID(r.Context(), acc.InstitutionID); err == nil {
		instName = inst.Name
	}

	// Get transactions filtered to this account (enriched with running balance)
	filter := repository.TransactionFilter{
		AccountID: id,
		Limit:     50,
	}
	rows, _ := h.txSvc.GetFilteredEnriched(r.Context(), filter)

	// Parse billing cycle for credit cards
	var billingCycle *service.BillingCycleInfo
	if acc.IsCreditType() {
		if meta := service.ParseBillingCycle(acc); meta != nil {
			info := service.GetBillingCycleInfo(*meta, timeutil.Now())
			billingCycle = &info
		}
	}

	// TASK-059: Fetch 30-day balance history for sparkline
	var balanceHistory []float64
	if h.snapshotSvc != nil {
		if history, err := h.snapshotSvc.GetAccountHistory(r.Context(), id, 30); err != nil {
			authmw.Log(r.Context()).Warn("failed to load balance history", "account_id", id, "error", err)
		} else {
			balanceHistory = history
		}
	}

	// TASK-073: Utilization for credit cards
	var utilization float64
	if acc.IsCreditType() {
		utilization = service.GetCreditCardUtilization(acc)
	}

	// TASK-076: Utilization trend from balance history
	var utilizationHistory []float64
	if acc.IsCreditType() && acc.CreditLimit != nil && *acc.CreditLimit > 0 && len(balanceHistory) >= 2 {
		for _, bal := range balanceHistory {
			used := -bal
			if used < 0 {
				used = 0
			}
			utilizationHistory = append(utilizationHistory, used / *acc.CreditLimit * 100)
		}
	}

	// Fetch linked virtual accounts for this bank account
	var virtualAccounts []models.VirtualAccount
	if h.virtualAccountSvc != nil {
		if vas, err := h.virtualAccountSvc.GetByAccountID(r.Context(), id); err != nil {
			authmw.Log(r.Context()).Warn("failed to load virtual accounts", "account_id", id, "error", err)
		} else {
			virtualAccounts = vas
		}
	}

	data := AccountDetailData{
		Account:            acc,
		InstitutionName:    instName,
		BillingCycle:       billingCycle,
		BalanceHistory:     balanceHistory,
		HealthConfig:       acc.GetHealthConfig(),
		Utilization:        utilization,
		UtilizationHistory: utilizationHistory,
		VirtualAccounts:    virtualAccounts,
		TransactionListData: TransactionListData{
			Transactions: toTransactionDisplay(rows, false),
			HasMore:      len(rows) >= filter.Limit,
			NextOffset:   filter.Limit,
			AccountID:    id,
		},
	}

	RenderPage(h.templates, w, "account-detail", PageData{ActiveTab: "accounts", Data: data})
}

// SuggestCategory returns the most likely category ID based on note text (TASK-079).
// GET /api/transactions/suggest-category?note=...
func (h *PageHandler) SuggestCategory(w http.ResponseWriter, r *http.Request) {
	note := r.URL.Query().Get("note")
	if note == "" {
		w.WriteHeader(http.StatusNoContent)
		return
	}

	categoryID := h.txSvc.SuggestCategory(r.Context(), note)
	if categoryID == "" {
		w.WriteHeader(http.StatusNoContent)
		return
	}

	w.Header().Set("Content-Type", "text/plain")
	w.Write([]byte(categoryID))
}

// CreditCardStatement renders the credit card statement view (TASK-071).
// GET /accounts/{id}/statement?period=YYYY-MM (optional)
func (h *PageHandler) CreditCardStatement(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "cc-statement")
	id := chi.URLParam(r, "id")
	periodStr := r.URL.Query().Get("period")

	acc, err := h.accountSvc.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, "account not found", http.StatusNotFound)
		return
	}

	if !acc.IsCreditType() {
		http.Error(w, "not a credit card account", http.StatusBadRequest)
		return
	}

	stmtData, err := service.GetStatementData(acc, h.txSvc.TxRepo(), h.snapshotSvc, r.Context(), periodStr)
	if err != nil {
		// BUG-008: show friendly message for missing billing cycle config
		RenderPage(h.templates, w, "credit-card-statement-error", PageData{
			ActiveTab: "accounts",
			Data: map[string]interface{}{
				"Account": acc,
				"Message": "Please configure a billing cycle (statement day & due day) in account settings to view your statement.",
			},
		})
		return
	}

	// TASK-073: Add utilization data
	utilization := service.GetCreditCardUtilization(acc)

	// Build utilization segment for the donut chart
	var utilSegments []models.ChartSegment
	if utilization > 0 {
		color := "#10b981" // emerald
		if utilization > 80 {
			color = "#dc2626" // red
		} else if utilization > 50 {
			color = "#f59e0b" // amber
		}
		utilSegments = []models.ChartSegment{{Label: "Used", Percentage: utilization, Color: color}}
	}

	type StatementPageData struct {
		Statement    *service.StatementData
		Utilization  float64
		UtilSegments []models.ChartSegment
	}

	RenderPage(h.templates, w, "credit-card-statement", PageData{
		ActiveTab: "accounts",
		Data:      StatementPageData{Statement: stmtData, Utilization: utilization, UtilSegments: utilSegments},
	})
}

// =============================================================================
// Quick Entry — Fast transaction creation from the dashboard
// =============================================================================

// QuickEntryForm serves the quick-entry form partial into the bottom sheet.
// GET /transactions/quick-form — loaded by HTMX when the FAB is tapped.
// Includes smart defaults: pre-selects last-used account and auto-selects category
// if the same one was used 3+ times consecutively.
func (h *PageHandler) QuickEntryForm(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "quick-entry-form")
	accounts, _ := h.accountSvc.GetAll(r.Context())
	expenseCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense)
	incomeCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeIncome)

	// Smart defaults from transaction history
	defaults := h.txSvc.GetSmartDefaults(r.Context(), "expense")

	var virtualAccounts []models.VirtualAccount
	if h.virtualAccountSvc != nil {
		virtualAccounts, _ = h.virtualAccountSvc.GetAll(r.Context())
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["home"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "quick-entry-form", QuickEntryData{
		TransactionFormData: TransactionFormData{
			Accounts:          accounts,
			ExpenseCategories: expenseCategories,
			IncomeCategories:  incomeCategories,
			VirtualAccounts:   virtualAccounts,
		},
		LastAccountID:  defaults.LastAccountID,
		AutoCategoryID: defaults.AutoCategoryID,
	})
}

// QuickExchangeForm serves the exchange form partial into the bottom sheet.
// GET /exchange/quick-form — loaded by HTMX when the "Exchange" tab is tapped.
func (h *PageHandler) QuickExchangeForm(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "quick-exchange-form")
	accounts, _ := h.accountSvc.GetAll(r.Context())

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["home"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "quick-exchange-form", TransactionFormData{
		Accounts: accounts,
		Today:    timeutil.Now(),
	})
}

// QuickTransferForm serves the transfer form partial into the bottom sheet.
// GET /transactions/quick-transfer — loaded by HTMX when the "Transfer" tab is tapped.
func (h *PageHandler) QuickTransferForm(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "quick-transfer-form")
	accounts, _ := h.accountSvc.GetAll(r.Context())

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["home"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "quick-transfer-form", TransactionFormData{
		Accounts: accounts,
		Today:    timeutil.Now(),
	})
}

// QuickEntryCreate handles the quick-entry form submission.
// POST /transactions/quick — returns success toast or error message.
func (h *PageHandler) QuickEntryCreate(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	tx := models.Transaction{
		Type:      models.TransactionType(r.FormValue("type")),
		Amount:    amount,
		Currency:  models.Currency(r.FormValue("currency")),
		AccountID: r.FormValue("account_id"),
	}
	if catID := r.FormValue("category_id"); catID != "" {
		tx.CategoryID = &catID
	}
	if note := r.FormValue("note"); note != "" {
		tx.Note = &note
	}
	if dateStr := r.FormValue("date"); dateStr != "" {
		if parsed, err := h.parseDate(dateStr); err == nil {
			tx.Date = parsed
		}
	}

	created, newBalance, err := h.txSvc.Create(r.Context(), tx)
	if err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	// Allocate to virtual account if selected (validate account linkage)
	if vaID := r.FormValue("virtual_account_id"); vaID != "" && h.virtualAccountSvc != nil {
		if va, err := h.virtualAccountSvc.GetByID(r.Context(), vaID); err == nil {
			if va.AccountID == nil || *va.AccountID == created.AccountID {
				allocAmount := created.Amount
				if created.Type == models.TransactionTypeExpense {
					allocAmount = -created.Amount
				}
				if err := h.virtualAccountSvc.Allocate(r.Context(), created.ID, vaID, allocAmount); err != nil {
					authmw.Log(r.Context()).Warn("virtual account allocation failed",
						"transaction_id", created.ID, "virtual_account_id", vaID, "error", err)
				}
			} else {
				authmw.Log(r.Context()).Warn("virtual account not linked to transaction account",
					"transaction_id", created.ID, "virtual_account_id", vaID,
					"va_account_id", *va.AccountID, "tx_account_id", created.AccountID)
			}
		}
	}

	cur := "EGP"
	if tx.Currency == models.CurrencyUSD {
		cur = "USD"
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["home"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "success-toast", TransactionSuccessData{
		Transaction: created,
		NewBalance:  newBalance,
		Currency:    cur,
	})
}

// =============================================================================
// Salary Wizard — Multi-step salary distribution flow
// =============================================================================
//
// The salary wizard is a 3-step HTMX-powered form:
//   Step 1: Enter salary amount (USD), select accounts, pick date
//   Step 2: Enter exchange rate (USD -> EGP)
//   Step 3: Allocate EGP amount across accounts (rent, savings, etc.)
//
// Each step POST returns the next step's HTML partial, which HTMX swaps in.
// This creates a smooth multi-step form without JavaScript state management.
// Like Laravel Livewire's multi-step form or Django's FormWizardView.

// Salary renders the salary distribution wizard page.
// GET /salary
func (h *PageHandler) Salary(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "salary")
	accounts, _ := h.accountSvc.GetAll(r.Context())
	RenderPage(h.templates, w, "salary", PageData{
		ActiveTab: "home",
		Data:      SalaryStepData{Accounts: accounts, Today: timeutil.Now()},
	})
}

// SalaryStep2 processes step 1 and renders the exchange rate step.
// POST /salary/step2
func (h *PageHandler) SalaryStep2(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	salaryUSD, _ := parseFloat(r.FormValue("salary_usd"))
	data := SalaryStepData{
		SalaryUSD:    salaryUSD,
		USDAccountID: r.FormValue("usd_account_id"),
		EGPAccountID: r.FormValue("egp_account_id"),
		Date:         r.FormValue("date"),
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["salary"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "salary-step2", data)
}

// SalaryStep3 processes step 2 and renders the allocation step.
// POST /salary/step3
func (h *PageHandler) SalaryStep3(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	salaryUSD, _ := parseFloat(r.FormValue("salary_usd"))
	exchangeRate, _ := parseFloat(r.FormValue("exchange_rate"))
	salaryEGP := salaryUSD * exchangeRate

	// Get all EGP accounts for allocation targets
	accounts, _ := h.accountSvc.GetAll(r.Context())
	var egpAccounts []models.Account
	for _, a := range accounts {
		if a.Currency == models.CurrencyEGP {
			egpAccounts = append(egpAccounts, a)
		}
	}

	data := SalaryStepData{
		SalaryUSD:    salaryUSD,
		ExchangeRate: exchangeRate,
		SalaryEGP:    salaryEGP,
		USDAccountID: r.FormValue("usd_account_id"),
		EGPAccountID: r.FormValue("egp_account_id"),
		Date:         r.FormValue("date"),
		EGPAccounts:  egpAccounts,
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["salary"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "salary-step3", data)
}

// SalaryConfirm processes the final step and creates all salary transactions.
// POST /salary/confirm
func (h *PageHandler) SalaryConfirm(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	salaryUSD, _ := parseFloat(r.FormValue("salary_usd"))
	exchangeRate, _ := parseFloat(r.FormValue("exchange_rate"))

	var date time.Time
	if d := r.FormValue("date"); d != "" {
		date, _ = h.parseDate(d)
	}

	// Collect allocations from form fields named alloc_<account_id>
	var allocations []service.SalaryAllocation
	for key, values := range r.Form {
		if !strings.HasPrefix(key, "alloc_") || len(values) == 0 {
			continue
		}
		accountID := strings.TrimPrefix(key, "alloc_")
		amount, _ := parseFloat(values[0])
		if amount > 0 {
			allocations = append(allocations, service.SalaryAllocation{
				AccountID: accountID,
				Amount:    amount,
			})
		}
	}

	dist := service.SalaryDistribution{
		SalaryUSD:    salaryUSD,
		ExchangeRate: exchangeRate,
		USDAccountID: r.FormValue("usd_account_id"),
		EGPAccountID: r.FormValue("egp_account_id"),
		Allocations:  allocations,
		Date:         date,
	}

	if err := h.salarySvc.DistributeSalary(r.Context(), dist); err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["salary"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "salary-success", SalarySuccessData{
		SalaryUSD:    salaryUSD,
		ExchangeRate: exchangeRate,
		SalaryEGP:    salaryUSD * exchangeRate,
		AllocCount:   len(allocations),
	})
}

// FawryCashout renders the Fawry cash-out form page.
// GET /fawry-cashout
func (h *PageHandler) FawryCashout(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "fawry-cashout")
	accounts, _ := h.accountSvc.GetAll(r.Context())
	RenderPage(h.templates, w, "fawry-cashout", PageData{
		ActiveTab: "home",
		Data:      TransactionFormData{Accounts: accounts, Today: timeutil.Now()},
	})
}

// FawryCashoutCreate handles the Fawry cash-out form submission.
// POST /transactions/fawry-cashout
func (h *PageHandler) FawryCashoutCreate(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	fee, _ := parseFloat(r.FormValue("fee"))
	creditCardID := r.FormValue("credit_card_id")
	prepaidAccountID := r.FormValue("prepaid_account_id")
	currency := models.Currency(r.FormValue("currency"))

	var note *string
	if n := r.FormValue("note"); n != "" {
		note = &n
	}

	var date time.Time
	if d := r.FormValue("date"); d != "" {
		date, _ = h.parseDate(d)
	}

	// Look up "Fees & Charges" category
	feesCatID := ""
	if cats, err := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense); err == nil {
		for _, c := range cats {
			if c.Name == "Fees & Charges" {
				feesCatID = c.ID
				break
			}
		}
	}

	_, _, err := h.txSvc.CreateFawryCashout(r.Context(), creditCardID, prepaidAccountID, amount, fee, currency, note, date, feesCatID)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		h.renderHTMXResult(w, "error", err.Error(), "")
		return
	}

	h.renderHTMXResult(w, "success", fmt.Sprintf("Fawry cash-out completed! Amount: EGP %.2f, Fee: EGP %.2f", amount, fee), "")
}

// =============================================================================
// Reports — Monthly spending breakdown with charts
// =============================================================================

// Reports renders the reports page with monthly spending breakdown.
// GET /reports
// GET /reports?year=2026&month=3&account_id=xxx&currency=EGP
//
// Features a donut chart (spending by category) and a 6-month bar chart
// (income vs expenses trend). Both charts use CSS-only rendering (see charts.go).
func (h *PageHandler) Reports(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "reports")
	now := timeutil.Now().In(h.loc)
	year, month := now.Year(), now.Month()

	// Parse optional year/month query params
	if v := r.URL.Query().Get("year"); v != "" {
		if y, err := strconv.Atoi(v); err == nil {
			year = y
		}
	}
	if v := r.URL.Query().Get("month"); v != "" {
		if m, err := strconv.Atoi(v); err == nil && m >= 1 && m <= 12 {
			month = time.Month(m)
		}
	}

	filter := service.ReportFilter{
		AccountID: r.URL.Query().Get("account_id"),
		Currency:  r.URL.Query().Get("currency"),
	}

	var data *service.ReportsData
	if h.reportsSvc != nil {
		report, err := h.reportsSvc.GetMonthlyReport(r.Context(), year, month, filter)
		if err == nil {
			data = &report
		}
	}

	RenderPage(h.templates, w, "reports", PageData{
		ActiveTab: "reports",
		Data:      data,
	})
}

// PeopleSummary renders the people summary partial for the dashboard.
// GET /partials/people-summary
func (h *PageHandler) PeopleSummary(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "people-summary")
	if h.dashboardSvc == nil {
		return
	}
	data, err := h.dashboardSvc.GetDashboard(r.Context())
	if err != nil {
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["home"]
	if !ok {
		return
	}
	tmpl.ExecuteTemplate(w, "people-summary", data)
}

// =============================================================================
// Recurring Rules — Auto-generated transactions on a schedule
// =============================================================================

// Recurring renders the recurring rules management page.
// GET /recurring
func (h *PageHandler) Recurring(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "recurring")
	ctx := r.Context()
	accounts, _ := h.accountSvc.GetAll(ctx)
	categories, _ := h.categorySvc.GetAll(ctx)

	var data *RecurringPageData
	if h.recurringSvc != nil {
		rules, _ := h.recurringSvc.GetAll(ctx)
		pending, _ := h.recurringSvc.GetDuePending(ctx)

		ruleViews := make([]RecurringRuleView, 0, len(rules))
		for _, rule := range rules {
			ruleViews = append(ruleViews, recurringRuleToView(rule))
		}
		pendingViews := make([]RecurringRuleView, 0, len(pending))
		for _, rule := range pending {
			pendingViews = append(pendingViews, recurringRuleToView(rule))
		}

		data = &RecurringPageData{
			Rules:        ruleViews,
			PendingRules: pendingViews,
			Accounts:     accounts,
			Categories:   categories,
			Today:        timeutil.Now(),
		}
	}

	RenderPage(h.templates, w, "recurring", PageData{ActiveTab: "home", Data: data})
}

// RecurringAdd creates a new recurring rule.
// POST /recurring/add
func (h *PageHandler) RecurringAdd(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	tmpl := models.TransactionTemplate{
		Type:     models.TransactionType(r.FormValue("type")),
		Amount:   amount,
		Currency: models.CurrencyEGP,
		AccountID: r.FormValue("account_id"),
	}
	if catID := r.FormValue("category_id"); catID != "" {
		tmpl.CategoryID = &catID
	}
	if note := r.FormValue("note"); note != "" {
		tmpl.Note = &note
	}

	// Look up account currency
	if acc, err := h.accountSvc.GetByID(r.Context(), tmpl.AccountID); err == nil {
		tmpl.Currency = acc.Currency
	}

	tmplJSON, err := json.Marshal(tmpl)
	if err != nil {
		authmw.Log(r.Context()).Error("failed to marshal recurring template", "error", err)
		http.Error(w, "failed to create rule", http.StatusInternalServerError)
		return
	}

	var nextDue time.Time
	if d := r.FormValue("next_due_date"); d != "" {
		nextDue, _ = h.parseDate(d)
	}

	rule := models.RecurringRule{
		TemplateTransaction: tmplJSON,
		Frequency:           models.RecurringFrequency(r.FormValue("frequency")),
		NextDueDate:         nextDue,
		IsActive:            true,
		AutoConfirm:         r.FormValue("auto_confirm") == "true",
	}

	_, err = h.recurringSvc.Create(r.Context(), rule)
	if err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	h.renderRecurringList(w, r)
}

// RecurringConfirm confirms a pending recurring rule and creates the transaction.
// POST /recurring/{id}/confirm
func (h *PageHandler) RecurringConfirm(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.recurringSvc.ConfirmRule(r.Context(), id); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	h.renderRecurringList(w, r)
}

// RecurringSkip skips a pending recurring rule without creating a transaction.
// POST /recurring/{id}/skip
func (h *PageHandler) RecurringSkip(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.recurringSvc.SkipRule(r.Context(), id); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	h.renderRecurringList(w, r)
}

// RecurringDelete deletes a recurring rule.
// DELETE /recurring/{id}
func (h *PageHandler) RecurringDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.recurringSvc.Delete(r.Context(), id); err != nil {
		authmw.Log(r.Context()).Error("failed to delete recurring rule", "id", id, "error", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.renderRecurringList(w, r)
}

// renderRecurringList renders the recurring rules list partial.
func (h *PageHandler) renderRecurringList(w http.ResponseWriter, r *http.Request) {
	rules, _ := h.recurringSvc.GetAll(r.Context())
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if len(rules) == 0 {
		w.Write([]byte(`<p class="text-sm text-gray-400 text-center">No recurring rules yet.</p>`))
		return
	}
	w.Write([]byte(`<div class="divide-y divide-gray-100">`))
	for _, rule := range rules {
		v := recurringRuleToView(rule)
		autoLabel := ""
		if v.AutoConfirm {
			autoLabel = ` <span class="text-teal-600">auto</span>`
		}
		fmt.Fprintf(w, `<div class="flex items-center justify-between py-2">
			<div>
				<p class="text-sm font-medium text-slate-700">%s</p>
				<p class="text-xs text-gray-400">%s &middot; Next: %s%s</p>
			</div>
			<div class="flex items-center gap-2">
				<span class="text-sm font-bold text-slate-800">%s</span>
				<button hx-delete="/recurring/%s" hx-target="#recurring-list" hx-swap="innerHTML"
						hx-confirm="Delete this rule?"
						class="text-red-400 hover:text-red-600 text-xs">Del</button>
			</div>
		</div>`, v.Note, v.Frequency, v.NextDueDate.Format("Jan 2, 2006"), autoLabel, v.Amount, v.ID)
	}
	w.Write([]byte(`</div>`))
}

// recurringRuleToView converts a recurring rule to a display-friendly view.
func recurringRuleToView(rule models.RecurringRule) RecurringRuleView {
	var tmpl models.TransactionTemplate
	_ = json.Unmarshal(rule.TemplateTransaction, &tmpl)

	note := ""
	if tmpl.Note != nil {
		note = *tmpl.Note
	}
	if note == "" {
		note = string(tmpl.Type)
	}

	return RecurringRuleView{
		ID:          rule.ID,
		Note:        note,
		Amount:      fmt.Sprintf("%.2f %s", tmpl.Amount, tmpl.Currency),
		Frequency:   string(rule.Frequency),
		NextDueDate: rule.NextDueDate,
		AutoConfirm: rule.AutoConfirm,
	}
}

// =============================================================================
// Offline Sync — Process transactions queued while offline (PWA feature)
// =============================================================================

// SyncTransactions handles batch sync of offline-queued transactions.
// POST /sync/transactions — accepts JSON array and creates each transaction.
//
// The PWA service worker queues transactions when offline, then sends them
// to this endpoint when connectivity is restored. Unlike other page handlers
// that use form data, this one accepts JSON (from the service worker's fetch).
func (h *PageHandler) SyncTransactions(w http.ResponseWriter, r *http.Request) {
	var payload struct {
		Transactions []struct {
			Type       string `json:"type"`
			Amount     string `json:"amount"`
			Currency   string `json:"currency"`
			AccountID  string `json:"account_id"`
			CategoryID string `json:"category_id"`
			Note       string `json:"note"`
			Date       string `json:"date"`
		} `json:"transactions"`
	}

	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}

	var created, failed int
	for _, t := range payload.Transactions {
		amount, _ := parseFloat(t.Amount)
		tx := models.Transaction{
			Type:     models.TransactionType(t.Type),
			Amount:   amount,
			Currency: models.Currency(t.Currency),
			AccountID: t.AccountID,
		}
		if t.CategoryID != "" {
			tx.CategoryID = &t.CategoryID
		}
		if t.Note != "" {
			tx.Note = &t.Note
		}
		if t.Date != "" {
			if parsed, err := h.parseDate(t.Date); err == nil {
				tx.Date = parsed
			}
		}

		if _, _, err := h.txSvc.Create(r.Context(), tx); err != nil {
			failed++
		} else {
			created++
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]int{
		"created": created,
		"failed":  failed,
	})
}

// InvestmentPageData holds data for the investments management page.
type InvestmentPageData struct {
	Investments    []models.Investment
	TotalValuation float64
}

// =============================================================================
// Investments Section — Portfolio tracking with units * price valuation
// =============================================================================

// Investments renders the investment portfolio page.
// GET /investments
func (h *PageHandler) Investments(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "investments")
	investments, _ := h.investmentSvc.GetAll(r.Context())
	total, _ := h.investmentSvc.GetTotalValuation(r.Context())

	data := InvestmentPageData{
		Investments:    investments,
		TotalValuation: total,
	}
	RenderPage(h.templates, w, "investments", PageData{ActiveTab: "more", Data: data})
}

// InvestmentAdd creates a new investment holding.
// POST /investments/add
//
// Uses HX-Redirect header pattern: after a successful creation, the server
// sets the HX-Redirect header and HTMX performs a client-side redirect.
// This is used when the entire page needs to refresh (not just a partial swap).
// Like Laravel's return redirect('/investments') but through an HTMX header.
func (h *PageHandler) InvestmentAdd(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	units, _ := parseFloat(r.FormValue("units"))
	unitPrice, _ := parseFloat(r.FormValue("unit_price"))

	inv := models.Investment{
		Platform:      r.FormValue("platform"),
		FundName:      r.FormValue("fund_name"),
		Units:         units,
		LastUnitPrice: unitPrice,
		Currency:      models.Currency(r.FormValue("currency")),
	}

	if _, err := h.investmentSvc.Create(r.Context(), inv); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	htmxRedirect(w, r, "/investments")
}

// InvestmentUpdateValuation updates the unit price for an investment.
// POST /investments/{id}/update
func (h *PageHandler) InvestmentUpdateValuation(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	r.ParseForm()
	unitPrice, _ := parseFloat(r.FormValue("unit_price"))

	if err := h.investmentSvc.UpdateValuation(r.Context(), id, unitPrice); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	htmxRedirect(w, r, "/investments")
}

// InvestmentDelete removes an investment holding.
// DELETE /investments/{id}
func (h *PageHandler) InvestmentDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.investmentSvc.Delete(r.Context(), id); err != nil {
		authmw.Log(r.Context()).Error("failed to delete investment", "id", id, "error", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	htmxRedirect(w, r, "/investments")
}

// InstallmentPageData holds data for the installment plans page.
type InstallmentPageData struct {
	Plans    []models.InstallmentPlan
	Accounts []models.Account
	Today    time.Time
}

// =============================================================================
// Installments Section — Payment plans with progress tracking
// =============================================================================

// Installments renders the installment plans page.
// GET /installments
func (h *PageHandler) Installments(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "installments")
	plans, _ := h.installmentSvc.GetAll(r.Context())
	accounts, _ := h.accountSvc.GetAll(r.Context())

	data := InstallmentPageData{Plans: plans, Accounts: accounts, Today: timeutil.Now()}
	RenderPage(h.templates, w, "installments", PageData{ActiveTab: "more", Data: data})
}

// InstallmentAdd creates a new installment plan.
// POST /installments/add
func (h *PageHandler) InstallmentAdd(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	totalAmount, _ := parseFloat(r.FormValue("total_amount"))
	numInstallments, _ := strconv.Atoi(r.FormValue("num_installments"))
	startDate, _ := h.parseDate(r.FormValue("start_date"))

	plan := models.InstallmentPlan{
		AccountID:       r.FormValue("account_id"),
		Description:     r.FormValue("description"),
		TotalAmount:     totalAmount,
		NumInstallments: numInstallments,
		StartDate:       startDate,
	}

	if _, err := h.installmentSvc.Create(r.Context(), plan); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	htmxRedirect(w, r, "/installments")
}

// InstallmentPay records a payment on an installment plan.
// POST /installments/{id}/pay
func (h *PageHandler) InstallmentPay(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.installmentSvc.RecordPayment(r.Context(), id); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	htmxRedirect(w, r, "/installments")
}

// InstallmentDelete removes an installment plan.
// DELETE /installments/{id}
func (h *PageHandler) InstallmentDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.installmentSvc.Delete(r.Context(), id); err != nil {
		authmw.Log(r.Context()).Error("failed to delete installment", "id", id, "error", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	htmxRedirect(w, r, "/installments")
}

// BatchEntryData holds data for the batch entry page.
type BatchEntryData struct {
	Accounts          []models.Account
	ExpenseCategories []models.Category
	Today             time.Time
}

// =============================================================================
// Batch Entry — Enter multiple transactions at once
// =============================================================================

// BatchEntry renders the batch entry page.
// GET /batch-entry
func (h *PageHandler) BatchEntry(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "batch-entry")
	accounts, _ := h.accountSvc.GetAll(r.Context())
	expCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense)

	data := BatchEntryData{Accounts: accounts, ExpenseCategories: expCategories, Today: timeutil.Now()}
	RenderPage(h.templates, w, "batch-entry", PageData{ActiveTab: "transactions", Data: data})
}

// BatchCreate processes multiple transactions from the batch entry form.
// POST /transactions/batch
//
// Form arrays in Go: HTML forms can send arrays using [] suffix:
//   <input name="type[]" value="expense">
//   <input name="type[]" value="income">
// r.Form["type[]"] returns []string{"expense", "income"} — a slice of all values.
// This is like PHP's $_POST['type'] returning an array.
func (h *PageHandler) BatchCreate(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()

	types := r.Form["type[]"]
	amounts := r.Form["amount[]"]
	accountIDs := r.Form["account_id[]"]
	categoryIDs := r.Form["category_id[]"]
	dates := r.Form["date[]"]
	notes := r.Form["note[]"]

	var created, failed int
	for i := range types {
		if i >= len(amounts) || i >= len(accountIDs) || i >= len(dates) {
			break
		}
		amount, err := parseFloat(amounts[i])
		if err != nil || amount <= 0 {
			failed++
			continue
		}
		date, err := h.parseDate(dates[i])
		if err != nil {
			failed++
			continue
		}

		tx := models.Transaction{
			Type:      models.TransactionType(types[i]),
			Amount:    amount,
			Currency:  models.CurrencyEGP,
			AccountID: accountIDs[i],
			Date:      date,
		}
		if i < len(categoryIDs) && categoryIDs[i] != "" {
			tx.CategoryID = &categoryIDs[i]
		}
		if i < len(notes) && notes[i] != "" {
			tx.Note = &notes[i]
		}

		if _, _, err := h.txSvc.Create(r.Context(), tx); err != nil {
			failed++
		} else {
			created++
		}
	}

	detail := ""
	if failed > 0 {
		detail = fmt.Sprintf("%d failed", failed)
	}
	h.renderHTMXResult(w, "info", fmt.Sprintf("Created %d transaction(s)", created), detail)
}

// ToggleDormant toggles the dormant status of an account.
// POST /accounts/{id}/dormant
func (h *PageHandler) ToggleDormant(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.accountSvc.ToggleDormant(r.Context(), id); err != nil {
		authmw.Log(r.Context()).Error("failed to toggle dormant", "account_id", id, "error", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	htmxRedirect(w, r, "/accounts/"+id)
}

// ReorderAccounts updates display_order for a list of account IDs.
// POST /accounts/reorder
func (h *PageHandler) ReorderAccounts(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	ids := r.Form["id[]"]
	for i, id := range ids {
		if err := h.accountSvc.UpdateDisplayOrder(r.Context(), id, i); err != nil {
			http.Error(w, "failed to reorder", http.StatusInternalServerError)
			return
		}
	}
	htmxRedirect(w, r, "/accounts")
}

// ReorderInstitutions updates display_order for a list of institution IDs.
// POST /institutions/reorder
func (h *PageHandler) ReorderInstitutions(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	ids := r.Form["id[]"]
	for i, id := range ids {
		if err := h.institutionSvc.UpdateDisplayOrder(r.Context(), id, i); err != nil {
			http.Error(w, "failed to reorder", http.StatusInternalServerError)
			return
		}
	}
	htmxRedirect(w, r, "/accounts")
}

// ExchangeRatePageData holds data for the exchange rate history page.
type ExchangeRatePageData struct {
	Rates []repository.ExchangeRateLog
}

// =============================================================================
// Exchange Rates — Historical rate log
// =============================================================================

// ExchangeRates renders the exchange rate history page.
// GET /exchange-rates
func (h *PageHandler) ExchangeRates(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "exchange-rates")
	var data ExchangeRatePageData
	if h.exchangeRateRepo != nil {
		rates, _ := h.exchangeRateRepo.GetAll(r.Context())
		data.Rates = rates
	}
	RenderPage(h.templates, w, "exchange-rates", PageData{ActiveTab: "reports", Data: data})
}

// =============================================================================
// Settings — PIN change, dark mode, CSV export, push notifications
// =============================================================================

// Settings renders the settings page.
// GET /settings
func (h *PageHandler) Settings(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "settings")
	RenderPage(h.templates, w, "settings", PageData{ActiveTab: "more"})
}

// ChangePin handles PIN change from the settings page.
// POST /settings/pin
func (h *PageHandler) ChangePin(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	currentPin := r.FormValue("current_pin")
	newPin := r.FormValue("new_pin")

	if len(newPin) < 4 {
		w.Write([]byte(`<p class="text-red-600 text-sm">PIN must be at least 4 digits</p>`))
		return
	}

	if h.authSvc == nil {
		w.Write([]byte(`<p class="text-red-600 text-sm">Auth service not available</p>`))
		return
	}

	if err := h.authSvc.ChangePin(r.Context(), currentPin, newPin); err != nil {
		w.Write([]byte(`<p class="text-red-600 text-sm">` + err.Error() + `</p>`))
		return
	}

	w.Write([]byte(`<p class="text-teal-600 text-sm font-medium">PIN changed successfully</p>`))
}

// ExportTransactions exports transactions as CSV file download.
// GET /export/transactions?from=2026-01-01&to=2026-03-31
//
// The Content-Disposition header triggers a file download in the browser.
// The ExportService writes CSV data directly to the ResponseWriter (streaming).
// This is like Laravel's Response::download() or Django's StreamingHttpResponse.
func (h *PageHandler) ExportTransactions(w http.ResponseWriter, r *http.Request) {
	fromStr := r.URL.Query().Get("from")
	toStr := r.URL.Query().Get("to")

	from, err := h.parseDate(fromStr)
	if err != nil {
		http.Error(w, "invalid 'from' date", http.StatusBadRequest)
		return
	}
	to, err := h.parseDate(toStr)
	if err != nil {
		http.Error(w, "invalid 'to' date", http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "text/csv")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=transactions_%s_%s.csv", fromStr, toStr))

	if err := h.exportSvc.ExportTransactionsCSV(r.Context(), w, from, to); err != nil {
		authmw.Log(r.Context()).Error("failed to export CSV", "error", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// =============================================================================
// Institution/Account CRUD — HTMX form handlers (HTML, not JSON)
// =============================================================================
//
// These handlers create institutions/accounts from HTML form submissions
// (not JSON). After creation, they re-render the entire institution list
// by calling InstitutionList() — HTMX swaps the updated list into the page.

// InstitutionAdd creates an institution from form data.
// POST /institutions/add — used by HTMX form submission.
// On success: returns success toast in #institution-form-area + OOB refresh of #institution-list.
// On error: returns error banner + re-rendered form in #institution-form-area.
func (h *PageHandler) InstitutionAdd(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form", http.StatusBadRequest)
		return
	}
	inst := models.Institution{
		Name: r.FormValue("name"),
		Type: models.InstitutionType(r.FormValue("type")),
	}
	if _, err := h.institutionSvc.Create(r.Context(), inst); err != nil {
		authmw.Log(r.Context()).Warn("institution create failed", "error", err)
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusUnprocessableEntity)
		if tmpl, ok := h.templates["accounts"]; ok {
			tmpl.ExecuteTemplate(w, "institution-form", InstitutionCreateData{Error: err.Error()})
		}
		return
	}

	// Success toast + close sheet + OOB refresh of the institution list
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<div class="bg-teal-50 border border-teal-200 rounded-xl p-3 text-center animate-toast">`)
	fmt.Fprint(w, `<p class="text-teal-800 font-semibold text-sm">Institution added!</p>`)
	fmt.Fprint(w, `</div>`)
	fmt.Fprint(w, `<script>setTimeout(function(){ closeCreateSheet(); }, 1000);</script>`)
	h.renderInstitutionListOOB(w, r)
}

// InstitutionDeleteConfirm returns the delete confirmation sheet content.
// GET /institutions/{id}/delete-confirm — loaded into the bottom sheet via HTMX.
func (h *PageHandler) InstitutionDeleteConfirm(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	inst, err := h.institutionSvc.GetByID(r.Context(), id)
	if err != nil {
		authmw.Log(r.Context()).Warn("institution not found for delete confirm", "id", id, "error", err)
		http.Error(w, "institution not found", http.StatusNotFound)
		return
	}
	accounts, _ := h.accountSvc.GetByInstitution(r.Context(), id)
	data := InstitutionDeleteData{
		InstitutionID:   inst.ID,
		InstitutionName: inst.Name,
		AccountCount:    len(accounts),
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["accounts"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "institution-delete-confirm", data)
}

// InstitutionDelete removes an institution and cascades to its accounts.
// DELETE /institutions/{id} — called from the delete confirmation sheet.
func (h *PageHandler) InstitutionDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.institutionSvc.Delete(r.Context(), id); err != nil {
		authmw.Log(r.Context()).Error("failed to delete institution", "id", id, "error", err)
		h.renderHTMXResult(w, "error", "Failed to delete institution", err.Error())
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<div class="bg-teal-50 border border-teal-200 rounded-xl p-3 text-center animate-toast">`)
	fmt.Fprint(w, `<p class="text-teal-800 font-semibold text-sm">Institution deleted!</p>`)
	fmt.Fprint(w, `</div>`)
	fmt.Fprint(w, `<script>setTimeout(function(){ closeDeleteSheet(); }, 1000);</script>`)
	h.renderInstitutionListOOB(w, r)
}

// AccountAdd creates an account from form data.
// POST /accounts/add — used by HTMX form submission.
// On success: returns success toast in #account-form-area + OOB refresh of #institution-list.
// On error: returns error banner + re-rendered form in #account-form-area.
func (h *PageHandler) AccountAdd(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form", http.StatusBadRequest)
		return
	}
	acc := models.Account{
		InstitutionID: r.FormValue("institution_id"),
		Name:          r.FormValue("name"),
		Type:          models.AccountType(r.FormValue("type")),
		Currency:      models.Currency(r.FormValue("currency")),
	}
	if v := r.FormValue("initial_balance"); v != "" {
		if f, err := parseFloat(v); err == nil {
			acc.InitialBalance = f
			acc.CurrentBalance = f
		}
	}
	if v := r.FormValue("credit_limit"); v != "" {
		if f, err := parseFloat(v); err == nil {
			acc.CreditLimit = &f
		}
	}
	if _, err := h.accountSvc.Create(r.Context(), acc); err != nil {
		authmw.Log(r.Context()).Warn("account create failed", "error", err)
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusUnprocessableEntity)
		if tmpl, ok := h.templates["accounts"]; ok {
			tmpl.ExecuteTemplate(w, "account-form", AccountFormData{
				InstitutionID:   r.FormValue("institution_id"),
				InstitutionName: r.FormValue("institution_name_display"),
				Error:           err.Error(),
			})
		}
		return
	}

	// Success: close the bottom sheet and refresh the institution list via OOB swap
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<script>closeAccountSheet();</script>`)
	h.renderInstitutionListOOB(w, r)
}

// InstitutionList renders just the institution list partial.
// GET /accounts/list — used by HTMX after creating an institution or account.
//
// Renders multiple "institution-card" templates in a loop — one per institution.
// Each card includes the institution's accounts. HTMX replaces the entire
// institution list container with this response.
func (h *PageHandler) InstitutionList(w http.ResponseWriter, r *http.Request) {
	institutions, err := h.institutionSvc.GetAll(r.Context())
	if err != nil {
		authmw.Log(r.Context()).Error("failed to load institutions", "error", err)
		http.Error(w, "failed to load institutions", http.StatusInternalServerError)
		return
	}

	var data []InstitutionWithAccounts
	for _, inst := range institutions {
		accounts, _ := h.accountSvc.GetByInstitution(r.Context(), inst.ID)
		data = append(data, InstitutionWithAccounts{
			Institution: inst,
			Accounts:    accounts,
		})
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["accounts"]
	if !ok {
		authmw.Log(r.Context()).Error("template not found", "template", "accounts")
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	for _, item := range data {
		tmpl.ExecuteTemplate(w, "institution-card", item)
	}
}

// renderInstitutionListOOB writes institution cards wrapped in an HTMX OOB swap div.
// This is appended to the response body after a success toast so HTMX updates
// #institution-list alongside the primary swap target (e.g., #account-form-area).
func (h *PageHandler) renderInstitutionListOOB(w http.ResponseWriter, r *http.Request) {
	institutions, err := h.institutionSvc.GetAll(r.Context())
	if err != nil {
		return
	}
	var data []InstitutionWithAccounts
	for _, inst := range institutions {
		accounts, _ := h.accountSvc.GetByInstitution(r.Context(), inst.ID)
		data = append(data, InstitutionWithAccounts{Institution: inst, Accounts: accounts})
	}
	tmpl, ok := h.templates["accounts"]
	if !ok {
		return
	}
	fmt.Fprint(w, `<div id="institution-list" class="space-y-3" hx-swap-oob="innerHTML">`)
	for _, item := range data {
		tmpl.ExecuteTemplate(w, "institution-card", item)
	}
	fmt.Fprint(w, `</div>`)
}

// InstitutionFormPartial returns just the institution form HTML.
// GET /accounts/institution-form — used to restore the form after a success toast auto-dismisses.
func (h *PageHandler) InstitutionFormPartial(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("partial loaded", "partial", "institution-form")
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if tmpl, ok := h.templates["accounts"]; ok {
		tmpl.ExecuteTemplate(w, "institution-form", InstitutionCreateData{})
	}
}

// InstitutionEditForm returns the edit form partial for the bottom sheet.
// GET /institutions/{id}/edit-form — loaded into the edit sheet via HTMX.
func (h *PageHandler) InstitutionEditForm(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	inst, err := h.institutionSvc.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, "institution not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["accounts"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "institution-edit-form", InstitutionEditData{
		Institution: inst,
	})
}

// InstitutionUpdate handles the institution edit form submission from the bottom sheet.
// PUT /institutions/{id} — on success, closes the sheet and refreshes the card via OOB swap.
func (h *PageHandler) InstitutionUpdate(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	inst := models.Institution{
		ID:   id,
		Name: r.FormValue("name"),
		Type: models.InstitutionType(r.FormValue("type")),
	}

	updated, err := h.institutionSvc.Update(r.Context(), inst)
	if err != nil {
		authmw.Log(r.Context()).Warn("institution update failed", "error", err)
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusUnprocessableEntity)
		tmpl, ok := h.templates["accounts"]
		if !ok {
			http.Error(w, "template not found", http.StatusInternalServerError)
			return
		}
		tmpl.ExecuteTemplate(w, "institution-edit-form", InstitutionEditData{
			Institution: inst,
			Error:       err.Error(),
		})
		return
	}

	// Success: close the sheet and refresh the card via OOB swap
	accounts, _ := h.accountSvc.GetByInstitution(r.Context(), updated.ID)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<script>closeEditSheet();</script>`)
	tmpl, ok := h.templates["accounts"]
	if !ok {
		return
	}
	fmt.Fprintf(w, `<div id="institution-%s" hx-swap-oob="outerHTML:#institution-%s">`, updated.ID, updated.ID)
	tmpl.ExecuteTemplate(w, "institution-card", InstitutionWithAccounts{
		Institution: updated,
		Accounts:    accounts,
	})
	fmt.Fprint(w, `</div>`)
}

// EmptyPartial returns an empty response — used to clear a container via HTMX.
// GET /accounts/empty — used by the auto-dismiss timer after success toasts.
func (h *PageHandler) EmptyPartial(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
}

// =============================================================================
// Virtual Accounts — Envelope budgeting system (TASK-062/063)
// =============================================================================
//
// Virtual accounts are like "envelopes" you allocate money into (vacation, emergency,
// wedding, etc.). They track progress toward a target amount. Transactions can
// be allocated to a virtual account, and its running balance is updated accordingly.
//
// This is similar to YNAB's envelope system or the "jars" budgeting method.

// VirtualAccountsPageData holds data for the virtual accounts list page.
type VirtualAccountsPageData struct {
	Accounts        []models.VirtualAccount
	BankAccounts    []models.Account       // for the "Linked Account" dropdown in create form
	AccountBalances map[string]float64     // account_id → bank account balance
	VAGroupTotals   map[string]float64     // account_id → sum of VA balances for that account
	Warnings        []string               // over-allocation warning messages
}

// VirtualAccountDetailData holds data for the virtual account detail page.
type VirtualAccountDetailData struct {
	Account              models.VirtualAccount
	Transactions         []models.Transaction
	Allocations          []models.VirtualAccountAllocation // direct + tx-linked allocations for history
	Today                time.Time
	LinkedAccount        *models.Account // linked bank account (for balance comparison)
	TotalVABalance       float64         // sum of all VA balances on same linked account
	OverAllocated        bool            // this VA's balance > linked account balance
	AccountOverAllocated bool            // total VA balance for this account > account balance
}

// VirtualAccounts renders the virtual accounts management page.
// GET /virtual-accounts
func (h *PageHandler) VirtualAccounts(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "virtual-accounts")
	if h.virtualAccountSvc == nil {
		RenderPage(h.templates, w, "virtual-accounts", PageData{ActiveTab: "home"})
		return
	}
	accounts, _ := h.virtualAccountSvc.GetAll(r.Context())
	bankAccounts, _ := h.accountSvc.GetAll(r.Context())

	// Build maps for over-allocation warnings
	accountBalances := make(map[string]float64)
	accountNames := make(map[string]string)
	for _, ba := range bankAccounts {
		accountBalances[ba.ID] = ba.CurrentBalance
		accountNames[ba.ID] = ba.Name
	}
	vaGroupTotals := make(map[string]float64)
	for _, va := range accounts {
		if va.AccountID != nil {
			vaGroupTotals[*va.AccountID] += va.CurrentBalance
		}
	}
	// Generate warning messages for over-allocated account groups
	var warnings []string
	for acctID, totalVA := range vaGroupTotals {
		if acctBal, ok := accountBalances[acctID]; ok && totalVA > acctBal {
			warnings = append(warnings, fmt.Sprintf(
				"Total virtual account allocations (EGP %.2f) exceed %s balance (EGP %.2f)",
				totalVA, accountNames[acctID], acctBal,
			))
		}
	}

	data := VirtualAccountsPageData{
		Accounts:        accounts,
		BankAccounts:    bankAccounts,
		AccountBalances: accountBalances,
		VAGroupTotals:   vaGroupTotals,
		Warnings:        warnings,
	}
	RenderPage(h.templates, w, "virtual-accounts", PageData{ActiveTab: "home", Data: data})
}

// VirtualAccountAdd creates a new virtual account from form data.
// POST /virtual-accounts/add
func (h *PageHandler) VirtualAccountAdd(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	a := models.VirtualAccount{
		Name:  r.FormValue("name"),
		Icon:  r.FormValue("icon"),
		Color: r.FormValue("color"),
	}
	if v := r.FormValue("target_amount"); v != "" {
		if amt, err := parseFloat(v); err == nil && amt > 0 {
			a.TargetAmount = &amt
		}
	}
	if acctID := r.FormValue("account_id"); acctID != "" {
		a.AccountID = &acctID
	}
	if _, err := h.virtualAccountSvc.Create(r.Context(), a); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	htmxRedirect(w, r, "/virtual-accounts")
}

// VirtualAccountDetail renders the virtual account detail page with transaction history.
// GET /virtual-accounts/{id}
func (h *PageHandler) VirtualAccountDetail(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "virtual-account-detail")
	id := chi.URLParam(r, "id")
	account, err := h.virtualAccountSvc.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, "virtual account not found", http.StatusNotFound)
		return
	}
	txns, _ := h.virtualAccountSvc.GetVirtualAccountTransactions(r.Context(), id, 50)
	allocs, _ := h.virtualAccountSvc.GetVirtualAccountAllocations(r.Context(), id, 50)

	data := VirtualAccountDetailData{
		Account:      account,
		Transactions: txns,
		Allocations:  allocs,
		Today:        timeutil.Now(),
	}

	// Compute over-allocation warnings if VA is linked to a bank account
	if account.AccountID != nil {
		if linkedAcct, err := h.accountSvc.GetByID(r.Context(), *account.AccountID); err == nil {
			data.LinkedAccount = &linkedAcct
			if account.CurrentBalance > linkedAcct.CurrentBalance {
				data.OverAllocated = true
			}
			// Sum all VA balances linked to the same bank account
			if siblingVAs, err := h.virtualAccountSvc.GetByAccountID(r.Context(), *account.AccountID); err == nil {
				for _, va := range siblingVAs {
					data.TotalVABalance += va.CurrentBalance
				}
				if data.TotalVABalance > linkedAcct.CurrentBalance {
					data.AccountOverAllocated = true
				}
			}
		}
	}

	RenderPage(h.templates, w, "virtual-account-detail", PageData{ActiveTab: "home", Data: data})
}

// VirtualAccountArchive archives a virtual account (soft-delete).
// POST /virtual-accounts/{id}/archive
func (h *PageHandler) VirtualAccountArchive(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.virtualAccountSvc.Archive(r.Context(), id); err != nil {
		authmw.Log(r.Context()).Error("failed to archive virtual account", "id", id, "error", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	htmxRedirect(w, r, "/virtual-accounts")
}

// VirtualAccountAllocate earmarks existing funds in a virtual account (no transaction created).
// POST /virtual-accounts/{id}/allocate
func (h *PageHandler) VirtualAccountAllocate(w http.ResponseWriter, r *http.Request) {
	vaID := chi.URLParam(r, "id")
	r.ParseForm()

	amount, err := parseFloat(r.FormValue("amount"))
	if err != nil || amount <= 0 {
		http.Error(w, "invalid amount", http.StatusBadRequest)
		return
	}

	// Determine allocation sign: contribution = positive, withdrawal = negative
	allocAmount := amount
	if r.FormValue("type") == "withdrawal" {
		allocAmount = -amount
	}

	note := r.FormValue("note")

	if err := h.virtualAccountSvc.DirectAllocate(r.Context(), vaID, allocAmount, note, timeutil.Now()); err != nil {
		authmw.Log(r.Context()).Warn("direct allocation failed", "virtual_account_id", vaID, "error", err)
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	htmxRedirect(w, r, "/virtual-accounts/"+vaID)
}

// =============================================================================
// Budgets — Monthly spending limits per category (TASK-065/066)
// =============================================================================
//
// Budgets set monthly spending limits for expense categories. The dashboard
// shows progress bars (green/amber/red) based on current spending vs the limit.
// Threshold alerts trigger at 80% (amber) and 100% (red).

// BudgetPageData holds data for the budget management page.
type BudgetPageData struct {
	Budgets    []models.BudgetWithSpending
	Categories []models.Category
}

// Budgets renders the budget management page.
// GET /budgets
func (h *PageHandler) Budgets(w http.ResponseWriter, r *http.Request) {
	authmw.Log(r.Context()).Info("page viewed", "page", "budgets")
	categories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense)
	var budgets []models.BudgetWithSpending
	if h.budgetSvc != nil {
		var err error
		budgets, err = h.budgetSvc.GetAllWithSpending(r.Context())
		if err != nil {
			authmw.Log(r.Context()).Error("failed to load budgets", "error", err)
		}
	}
	data := BudgetPageData{Budgets: budgets, Categories: categories}
	RenderPage(h.templates, w, "budgets", PageData{ActiveTab: "more", Data: data})
}

// BudgetAdd creates a new budget from form data.
// POST /budgets/add
func (h *PageHandler) BudgetAdd(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	limit, _ := parseFloat(r.FormValue("monthly_limit"))
	b := models.Budget{
		CategoryID:   r.FormValue("category_id"),
		MonthlyLimit: limit,
		Currency:     models.Currency(r.FormValue("currency")),
	}
	if _, err := h.budgetSvc.Create(r.Context(), b); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	http.Redirect(w, r, "/budgets", http.StatusSeeOther)
}

// BudgetDelete removes a budget.
// POST /budgets/{id}/delete
func (h *PageHandler) BudgetDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.budgetSvc.Delete(r.Context(), id); err != nil {
		authmw.Log(r.Context()).Error("failed to delete budget", "id", id, "error", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	http.Redirect(w, r, "/budgets", http.StatusSeeOther)
}

// =============================================================================
// Account Health — Min balance and min deposit constraints (TASK-068/069)
// =============================================================================
//
// Account health rules let the user set constraints:
//   - MinBalance: warn if account drops below this amount
//   - MinMonthlyDeposit: warn if monthly deposits are below this threshold
// Warnings appear on the dashboard and can trigger push notifications.

// AccountHealthUpdate saves health constraints for an account.
// POST /accounts/{id}/health
func (h *PageHandler) AccountHealthUpdate(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	r.ParseForm()

	var cfg models.AccountHealthConfig
	if v := r.FormValue("min_balance"); v != "" {
		if f, err := parseFloat(v); err == nil && f > 0 {
			cfg.MinBalance = &f
		}
	}
	if v := r.FormValue("min_monthly_deposit"); v != "" {
		if f, err := parseFloat(v); err == nil && f > 0 {
			cfg.MinMonthlyDeposit = &f
		}
	}

	if h.healthSvc != nil {
		if err := h.healthSvc.UpdateHealthConfig(r.Context(), id, cfg); err != nil {
			authmw.Log(r.Context()).Error("failed to update health config", "account_id", id, "error", err)
		}
	}

	htmxRedirect(w, r, "/accounts/"+id)
}

// AccountDelete removes an account and all its cascading data (transactions, snapshots).
// DELETE /accounts/{id} — called from the confirmation bottom sheet on the account detail page.
func (h *PageHandler) AccountDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.accountSvc.Delete(r.Context(), id); err != nil {
		// FK violation — installment plans use RESTRICT, not CASCADE
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23503" {
			h.renderHTMXResult(w, "error",
				"Cannot delete: active installment plans exist",
				"Delete or complete the installment plans first, then try again.")
			return
		}
		if errors.Is(err, sql.ErrNoRows) {
			http.Error(w, "account not found", http.StatusNotFound)
			return
		}
		authmw.Log(r.Context()).Error("failed to delete account", "id", id, "error", err)
		h.renderHTMXResult(w, "error", "Failed to delete account", "")
		return
	}
	htmxRedirect(w, r, "/accounts")
}
