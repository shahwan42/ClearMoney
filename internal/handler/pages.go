package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"

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
	// Pre-fill fields (for transaction duplication)
	Prefill *models.Transaction
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

// TransactionEditData holds data for the inline edit form.
type TransactionEditData struct {
	Transaction        models.Transaction
	Categories         []models.Category
	SelectedCategoryID string
}

// TransactionSuccessData is shown after a successful transaction creation.
type TransactionSuccessData struct {
	Transaction models.Transaction
	NewBalance  float64
	Currency    string
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

// BuildingFundPageData holds data for the building fund sub-ledger page.
type BuildingFundPageData struct {
	Balance      float64
	Transactions []models.Transaction
	Accounts     []models.Account
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
}

// SalarySuccessData holds data for the salary success confirmation.
type SalarySuccessData struct {
	SalaryUSD    float64
	ExchangeRate float64
	SalaryEGP    float64
	AllocCount   int
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
	personSvc      *service.PersonService
	salarySvc      *service.SalaryService
	reportsSvc     *service.ReportsService
	recurringSvc   *service.RecurringService
	investmentSvc   *service.InvestmentService
	installmentSvc  *service.InstallmentService
}

func NewPageHandler(templates TemplateMap, institutionSvc *service.InstitutionService, accountSvc *service.AccountService, categorySvc *service.CategoryService, txSvc *service.TransactionService, dashboardSvc *service.DashboardService, personSvc *service.PersonService, salarySvc *service.SalaryService, reportsSvc *service.ReportsService, recurringSvc *service.RecurringService, investmentSvc *service.InvestmentService, installmentSvc *service.InstallmentService) *PageHandler {
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
// Supports ?dup=<id> to pre-fill from an existing transaction (duplication).
func (h *PageHandler) TransactionNew(w http.ResponseWriter, r *http.Request) {
	accounts, err := h.accountSvc.GetAll(r.Context())
	if err != nil {
		accounts = []models.Account{}
	}
	expenseCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense)
	incomeCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeIncome)

	data := TransactionFormData{
		Accounts:          accounts,
		ExpenseCategories: expenseCategories,
		IncomeCategories:  incomeCategories,
	}

	// If ?dup=<id> is provided, pre-fill from that transaction
	if dupID := r.URL.Query().Get("dup"); dupID != "" {
		if tx, err := h.txSvc.GetByID(r.Context(), dupID); err == nil {
			data.Prefill = &tx
		}
	}

	RenderPage(h.templates, w, "transaction-new", PageData{
		ActiveTab: "home",
		Data:      data,
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

// TransferNew renders the transfer form page.
// GET /transfers/new
func (h *PageHandler) TransferNew(w http.ResponseWriter, r *http.Request) {
	accounts, _ := h.accountSvc.GetAll(r.Context())
	RenderPage(h.templates, w, "transaction-new", PageData{
		ActiveTab: "home",
		Data: TransactionFormData{
			Accounts: accounts,
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
		date, _ = parseDate(d)
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
		date, _ = parseDate(d)
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
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(fmt.Sprintf(
		`<div class="bg-green-50 text-green-700 p-3 rounded-lg text-sm">InstaPay transfer completed! Fee: EGP %.2f</div>`,
		fee,
	)))
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
		if t, err := parseDate(v); err == nil {
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
	w.Write([]byte(`<div class="bg-green-50 text-green-700 p-3 rounded-lg text-sm">Exchange completed successfully!</div>`))
}

// TransactionEditForm renders the inline edit form for a transaction.
// GET /transactions/edit/{id} — called by HTMX.
func (h *PageHandler) TransactionEditForm(w http.ResponseWriter, r *http.Request) {
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

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["transactions"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "transaction-edit-form", TransactionEditData{
		Transaction:        tx,
		Categories:         categories,
		SelectedCategoryID: selectedCatID,
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
		if parsed, err := parseDate(dateStr); err == nil {
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

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["transactions"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "transaction-row", updated)
}

// TransactionDelete handles transaction deletion from the UI.
// DELETE /transactions/{id} — called by HTMX, returns empty (row removed).
func (h *PageHandler) TransactionDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.txSvc.Delete(r.Context(), id); err != nil {
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
	tx, err := h.txSvc.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["transactions"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "transaction-row", tx)
}

// People renders the people ledger page.
// GET /people
func (h *PageHandler) People(w http.ResponseWriter, r *http.Request) {
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

// RecentTransactions renders just the recent transactions partial.
// GET /partials/recent-transactions — used by HTMX to refresh the dashboard feed.
func (h *PageHandler) RecentTransactions(w http.ResponseWriter, r *http.Request) {
	txns, _ := h.txSvc.GetRecent(r.Context(), 15)

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["home"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "recent-transactions", txns)
}

// AccountDetail renders the account detail page with transaction history.
// GET /accounts/{id}
func (h *PageHandler) AccountDetail(w http.ResponseWriter, r *http.Request) {
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

	// Get transactions filtered to this account
	filter := repository.TransactionFilter{
		AccountID: id,
		Limit:     50,
	}
	txns, _ := h.txSvc.GetFiltered(r.Context(), filter)

	// Parse billing cycle for credit cards
	var billingCycle *service.BillingCycleInfo
	if acc.IsCreditType() {
		if meta := service.ParseBillingCycle(acc); meta != nil {
			info := service.GetBillingCycleInfo(*meta, time.Now())
			billingCycle = &info
		}
	}

	data := AccountDetailData{
		Account:         acc,
		InstitutionName: instName,
		BillingCycle:    billingCycle,
		TransactionListData: TransactionListData{
			Transactions: txns,
			HasMore:      len(txns) >= filter.Limit,
			NextOffset:   filter.Limit,
			AccountID:    id,
		},
	}

	RenderPage(h.templates, w, "account-detail", PageData{ActiveTab: "accounts", Data: data})
}

// QuickEntryForm serves the quick-entry form partial into the bottom sheet.
// GET /transactions/quick-form — loaded by HTMX when the FAB is tapped.
// Includes smart defaults: pre-selects last-used account and auto-selects category
// if the same one was used 3+ times consecutively.
func (h *PageHandler) QuickEntryForm(w http.ResponseWriter, r *http.Request) {
	accounts, _ := h.accountSvc.GetAll(r.Context())
	expenseCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense)
	incomeCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeIncome)

	// Smart defaults from transaction history
	defaults := h.txSvc.GetSmartDefaults(r.Context(), "expense")

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
		},
		LastAccountID:  defaults.LastAccountID,
		AutoCategoryID: defaults.AutoCategoryID,
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

// Salary renders the salary distribution wizard page.
// GET /salary
func (h *PageHandler) Salary(w http.ResponseWriter, r *http.Request) {
	accounts, _ := h.accountSvc.GetAll(r.Context())
	RenderPage(h.templates, w, "salary", PageData{
		ActiveTab: "home",
		Data:      SalaryStepData{Accounts: accounts},
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
		date, _ = parseDate(d)
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
	accounts, _ := h.accountSvc.GetAll(r.Context())
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	tmpl, ok := h.templates["transaction-new"]
	if !ok {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	tmpl.ExecuteTemplate(w, "fawry-cashout-form", TransactionFormData{Accounts: accounts})
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
		date, _ = parseDate(d)
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
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(fmt.Sprintf(
		`<div class="bg-green-50 text-green-700 p-3 rounded-lg text-sm">Fawry cash-out completed! Amount: EGP %.2f, Fee: EGP %.2f</div>`,
		amount, fee,
	)))
}

// Reports renders the reports page with monthly spending breakdown.
// GET /reports
func (h *PageHandler) Reports(w http.ResponseWriter, r *http.Request) {
	now := time.Now()
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

	var data *service.ReportsData
	if h.reportsSvc != nil {
		report, err := h.reportsSvc.GetMonthlyReport(r.Context(), year, month)
		if err == nil {
			data = &report
		}
	}

	RenderPage(h.templates, w, "reports", PageData{
		ActiveTab: "reports",
		Data:      data,
	})
}

// BuildingFundPage renders the building fund sub-ledger page.
// GET /building-fund
func (h *PageHandler) BuildingFundPage(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	balance, _ := h.txSvc.GetBuildingFundBalance(ctx)
	txns, _ := h.txSvc.GetBuildingFundTransactions(ctx, 100)
	accounts, _ := h.accountSvc.GetAll(ctx)

	RenderPage(h.templates, w, "building-fund", PageData{
		ActiveTab: "home",
		Data: BuildingFundPageData{
			Balance:      balance,
			Transactions: txns,
			Accounts:     accounts,
		},
	})
}

// BuildingFundAdd handles the building fund collection/expense form.
// POST /building-fund/add
func (h *PageHandler) BuildingFundAdd(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid form data", http.StatusBadRequest)
		return
	}

	amount, _ := parseFloat(r.FormValue("amount"))
	tx := models.Transaction{
		Type:           models.TransactionType(r.FormValue("type")),
		Amount:         amount,
		Currency:       models.CurrencyEGP,
		AccountID:      r.FormValue("account_id"),
		IsBuildingFund: true,
	}
	if note := r.FormValue("note"); note != "" {
		tx.Note = &note
	}
	if dateStr := r.FormValue("date"); dateStr != "" {
		if parsed, err := parseDate(dateStr); err == nil {
			tx.Date = parsed
		}
	}

	_, _, err := h.txSvc.Create(r.Context(), tx)
	if err != nil {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">` + err.Error() + `</div>`))
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(`<div class="bg-green-50 text-green-700 p-3 rounded-lg text-sm">Building fund entry recorded! <a href="/building-fund" class="underline">Refresh page</a></div>`))
}

// PeopleSummary renders the people summary partial for the dashboard.
// GET /partials/people-summary
func (h *PageHandler) PeopleSummary(w http.ResponseWriter, r *http.Request) {
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

// BuildingFund renders the building fund partial for the dashboard.
// GET /partials/building-fund
func (h *PageHandler) BuildingFund(w http.ResponseWriter, r *http.Request) {
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
	tmpl.ExecuteTemplate(w, "building-fund", data)
}

// Recurring renders the recurring rules management page.
// GET /recurring
func (h *PageHandler) Recurring(w http.ResponseWriter, r *http.Request) {
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

	tmplJSON, _ := json.Marshal(tmpl)

	var nextDue time.Time
	if d := r.FormValue("next_due_date"); d != "" {
		nextDue, _ = parseDate(d)
	}

	rule := models.RecurringRule{
		TemplateTransaction: tmplJSON,
		Frequency:           models.RecurringFrequency(r.FormValue("frequency")),
		NextDueDate:         nextDue,
		IsActive:            true,
		AutoConfirm:         r.FormValue("auto_confirm") == "true",
	}

	_, err := h.recurringSvc.Create(r.Context(), rule)
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
		w.Write([]byte(fmt.Sprintf(`<div class="flex items-center justify-between py-2">
			<div>
				<p class="text-sm font-medium text-slate-700">%s</p>
				<p class="text-xs text-gray-400">%s &middot; Next: %s</p>
			</div>
			<div class="flex items-center gap-2">
				<span class="text-sm font-bold text-slate-800">%s</span>
			</div>
		</div>`, v.Note, v.Frequency, v.NextDueDate.Format("Jan 2, 2006"), v.Amount)))
	}
	w.Write([]byte(`</div>`))
}

// recurringRuleToView converts a recurring rule to a display-friendly view.
func recurringRuleToView(rule models.RecurringRule) RecurringRuleView {
	var tmpl models.TransactionTemplate
	json.Unmarshal(rule.TemplateTransaction, &tmpl)

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

// SyncTransactions handles batch sync of offline-queued transactions.
// POST /sync/transactions — accepts JSON array and creates each transaction.
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
			if parsed, err := parseDate(t.Date); err == nil {
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

// Investments renders the investment portfolio page.
// GET /investments
func (h *PageHandler) Investments(w http.ResponseWriter, r *http.Request) {
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

	w.Header().Set("HX-Redirect", "/investments")
	w.WriteHeader(http.StatusOK)
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

	w.Header().Set("HX-Redirect", "/investments")
	w.WriteHeader(http.StatusOK)
}

// InvestmentDelete removes an investment holding.
// DELETE /investments/{id}
func (h *PageHandler) InvestmentDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.investmentSvc.Delete(r.Context(), id); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("HX-Redirect", "/investments")
	w.WriteHeader(http.StatusOK)
}

// InstallmentPageData holds data for the installment plans page.
type InstallmentPageData struct {
	Plans    []models.InstallmentPlan
	Accounts []models.Account
}

// Installments renders the installment plans page.
// GET /installments
func (h *PageHandler) Installments(w http.ResponseWriter, r *http.Request) {
	plans, _ := h.installmentSvc.GetAll(r.Context())
	accounts, _ := h.accountSvc.GetAll(r.Context())

	data := InstallmentPageData{Plans: plans, Accounts: accounts}
	RenderPage(h.templates, w, "installments", PageData{ActiveTab: "more", Data: data})
}

// InstallmentAdd creates a new installment plan.
// POST /installments/add
func (h *PageHandler) InstallmentAdd(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()
	totalAmount, _ := parseFloat(r.FormValue("total_amount"))
	numInstallments, _ := strconv.Atoi(r.FormValue("num_installments"))
	startDate, _ := parseDate(r.FormValue("start_date"))

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

	w.Header().Set("HX-Redirect", "/installments")
	w.WriteHeader(http.StatusOK)
}

// InstallmentPay records a payment on an installment plan.
// POST /installments/{id}/pay
func (h *PageHandler) InstallmentPay(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.installmentSvc.RecordPayment(r.Context(), id); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.Header().Set("HX-Redirect", "/installments")
	w.WriteHeader(http.StatusOK)
}

// InstallmentDelete removes an installment plan.
// DELETE /installments/{id}
func (h *PageHandler) InstallmentDelete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.installmentSvc.Delete(r.Context(), id); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("HX-Redirect", "/installments")
	w.WriteHeader(http.StatusOK)
}

// BatchEntryData holds data for the batch entry page.
type BatchEntryData struct {
	Accounts          []models.Account
	ExpenseCategories []models.Category
}

// BatchEntry renders the batch entry page.
// GET /batch-entry
func (h *PageHandler) BatchEntry(w http.ResponseWriter, r *http.Request) {
	accounts, _ := h.accountSvc.GetAll(r.Context())
	expCategories, _ := h.categorySvc.GetByType(r.Context(), models.CategoryTypeExpense)

	data := BatchEntryData{Accounts: accounts, ExpenseCategories: expCategories}
	RenderPage(h.templates, w, "batch-entry", PageData{ActiveTab: "transactions", Data: data})
}

// BatchCreate processes multiple transactions from the batch entry form.
// POST /transactions/batch
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
		date, err := parseDate(dates[i])
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

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprintf(w, `<div class="bg-teal-50 border border-teal-200 rounded-xl p-4 text-center">
		<p class="text-sm font-medium text-teal-800">Created %d transaction(s)</p>
		%s
	</div>`, created, func() string {
		if failed > 0 {
			return fmt.Sprintf(`<p class="text-xs text-red-600 mt-1">%d failed</p>`, failed)
		}
		return ""
	}())
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
