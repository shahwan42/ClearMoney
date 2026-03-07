package handler

import (
	"fmt"
	"net/http"
	"strconv"
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
	TransactionListData TransactionListData
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
}

func NewPageHandler(templates TemplateMap, institutionSvc *service.InstitutionService, accountSvc *service.AccountService, categorySvc *service.CategoryService, txSvc *service.TransactionService, dashboardSvc *service.DashboardService, personSvc *service.PersonService) *PageHandler {
	return &PageHandler{
		templates:      templates,
		institutionSvc: institutionSvc,
		accountSvc:     accountSvc,
		categorySvc:    categorySvc,
		txSvc:          txSvc,
		dashboardSvc:   dashboardSvc,
		personSvc:      personSvc,
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

	data := AccountDetailData{
		Account:         acc,
		InstitutionName: instName,
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
