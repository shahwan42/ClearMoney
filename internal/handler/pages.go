package handler

import (
	"net/http"
	"strconv"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

func parseFloat(s string) (float64, error) {
	return strconv.ParseFloat(s, 64)
}

func parseDate(s string) (time.Time, error) {
	return time.Parse("2006-01-02", s)
}

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
}

// TransactionFormData holds data for the transaction entry form dropdowns.
type TransactionFormData struct {
	Accounts           []models.Account
	ExpenseCategories  []models.Category
	IncomeCategories   []models.Category
}

// TransactionListData holds data for the transaction list page and partial.
type TransactionListData struct {
	Transactions []models.Transaction
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
}

// TransactionSuccessData is shown after a successful transaction creation.
type TransactionSuccessData struct {
	Transaction models.Transaction
	NewBalance  float64
	Currency    string
}

// PageHandler serves full HTML pages (as opposed to JSON API endpoints).
// Think of it like Laravel's web routes vs API routes — same data, different format.
type PageHandler struct {
	templates      TemplateMap
	institutionSvc *service.InstitutionService
	accountSvc     *service.AccountService
	categorySvc    *service.CategoryService
	txSvc          *service.TransactionService
	dashboardSvc   *service.DashboardService
}

func NewPageHandler(templates TemplateMap, institutionSvc *service.InstitutionService, accountSvc *service.AccountService, categorySvc *service.CategoryService, txSvc *service.TransactionService, dashboardSvc *service.DashboardService) *PageHandler {
	return &PageHandler{
		templates:      templates,
		institutionSvc: institutionSvc,
		accountSvc:     accountSvc,
		categorySvc:    categorySvc,
		txSvc:          txSvc,
		dashboardSvc:   dashboardSvc,
	}
}

// Home renders the dashboard page.
// GET /
func (h *PageHandler) Home(w http.ResponseWriter, r *http.Request) {
	var data any
	if h.dashboardSvc != nil {
		dashData, err := h.dashboardSvc.GetDashboard(r.Context())
		if err == nil {
			data = dashData
		}
	}
	RenderPage(h.templates, w, "home", PageData{ActiveTab: "home", Data: data})
}

// Accounts renders the accounts management page.
// GET /accounts
func (h *PageHandler) Accounts(w http.ResponseWriter, r *http.Request) {
	institutions, err := h.institutionSvc.GetAll(r.Context())
	if err != nil {
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

	RenderPage(h.templates, w, "accounts", PageData{ActiveTab: "home", Data: data})
}

// AccountForm renders the account creation form for a specific institution.
// GET /accounts/form?institution_id=xxx — called by HTMX.
func (h *PageHandler) AccountForm(w http.ResponseWriter, r *http.Request) {
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

// TransactionNew renders the transaction entry form.
// GET /transactions/new
func (h *PageHandler) TransactionNew(w http.ResponseWriter, r *http.Request) {
	accounts, err := h.accountSvc.GetAll(r.Context())
	if err != nil {
		accounts = []models.Account{}
	}
	expenseCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense)
	incomeCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeIncome)

	RenderPage(h.templates, w, "transaction-new", PageData{
		ActiveTab: "home",
		Data: TransactionFormData{
			Accounts:          accounts,
			ExpenseCategories: expenseCategories,
			IncomeCategories:  incomeCategories,
		},
	})
}

// TransactionCreate handles the HTMX form submission for creating a transaction.
// POST /transactions — returns success partial or error.
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
		if parsed, err := parseDate(dateStr); err == nil {
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
func (h *PageHandler) Transactions(w http.ResponseWriter, r *http.Request) {
	filter := h.parseTransactionFilter(r)

	txns, _ := h.txSvc.GetFiltered(r.Context(), filter)
	accounts, _ := h.accountSvc.GetAll(r.Context())
	categories, _ := h.categorySvc.GetAll(r.Context())

	data := TransactionListData{
		Transactions: txns,
		Accounts:     accounts,
		Categories:   categories,
		HasMore:      len(txns) >= filter.Limit,
		NextOffset:   filter.Offset + filter.Limit,
		AccountID:    filter.AccountID,
		CategoryID:   filter.CategoryID,
		Type:         filter.Type,
		DateFrom:     r.URL.Query().Get("date_from"),
		DateTo:       r.URL.Query().Get("date_to"),
	}

	RenderPage(h.templates, w, "transactions", PageData{ActiveTab: "home", Data: data})
}

// TransactionList renders just the transaction list partial (for HTMX filter updates).
// GET /transactions/list
func (h *PageHandler) TransactionList(w http.ResponseWriter, r *http.Request) {
	filter := h.parseTransactionFilter(r)
	txns, _ := h.txSvc.GetFiltered(r.Context(), filter)

	data := TransactionListData{
		Transactions: txns,
		HasMore:      len(txns) >= filter.Limit,
		NextOffset:   filter.Offset + filter.Limit,
		AccountID:    filter.AccountID,
		CategoryID:   filter.CategoryID,
		Type:         filter.Type,
		DateFrom:     r.URL.Query().Get("date_from"),
		DateTo:       r.URL.Query().Get("date_to"),
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
		Limit:      50,
	}

	if v := q.Get("offset"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			f.Offset = n
		}
	}
	if v := q.Get("date_from"); v != "" {
		if t, err := parseDate(v); err == nil {
			f.DateFrom = &t
		}
	}
	if v := q.Get("date_to"); v != "" {
		if t, err := parseDate(v); err == nil {
			f.DateTo = &t
		}
	}

	return f
}

// InstitutionList renders just the institution list partial.
// Used by HTMX after creating an institution or account to refresh the list.
func (h *PageHandler) InstitutionList(w http.ResponseWriter, r *http.Request) {
	institutions, err := h.institutionSvc.GetAll(r.Context())
	if err != nil {
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
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	for _, item := range data {
		tmpl.ExecuteTemplate(w, "institution-card", item)
	}
}
