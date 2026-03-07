package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/templates"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func TestHomePage_Renders(t *testing.T) {
	tmpl, err := ParseTemplates(templates.FS)
	if err != nil {
		t.Fatalf("parsing templates: %v", err)
	}

	pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	pages.Home(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()

	// Verify key layout elements are present (no DB = empty state)
	checks := []string{
		"ClearMoney",          // header
		"tailwindcss",         // Tailwind CDN
		"htmx.org",            // HTMX script
		"Net Worth",           // dashboard section (empty state)
		"/static/css/app.css",      // custom CSS link
		"/static/manifest.json",    // PWA manifest
		"serviceWorker",            // SW registration
	}
	for _, check := range checks {
		if !strings.Contains(body, check) {
			t.Errorf("expected page to contain %q", check)
		}
	}
}

func TestHomePage_ContentType(t *testing.T) {
	tmpl, err := ParseTemplates(templates.FS)
	if err != nil {
		t.Fatalf("parsing templates: %v", err)
	}

	pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	pages.Home(w, req)

	ct := w.Header().Get("Content-Type")
	if !strings.Contains(ct, "text/html") {
		t.Errorf("expected text/html content type, got %q", ct)
	}
}

func TestHomePage_ActiveTab(t *testing.T) {
	tmpl, err := ParseTemplates(templates.FS)
	if err != nil {
		t.Fatalf("parsing templates: %v", err)
	}

	pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	pages.Home(w, req)

	body := w.Body.String()
	// The home tab should have the active color (teal-600)
	if !strings.Contains(body, "text-teal-600") {
		t.Error("expected home tab to be active (text-teal-600)")
	}
}

func TestAccountsPage_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	// Create an institution with an account
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})

	router, addAuth := testRouter(t, db)
	req := httptest.NewRequest(http.MethodGet, "/accounts", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	checks := []string{
		"HSBC",                // institution name
		"Checking",            // account name
		"Add Institution",     // form button
		"EGP",                 // currency display
	}
	for _, check := range checks {
		if !strings.Contains(body, check) {
			t.Errorf("expected accounts page to contain %q", check)
		}
	}
}

func TestAccountsPage_Empty(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	router, addAuth := testRouter(t, db)
	req := httptest.NewRequest(http.MethodGet, "/accounts", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "No institutions yet") {
		t.Error("expected empty state message")
	}
}

func TestTransactionNewPage_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	// Create an account so the dropdown has data
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID,
		Name:          "Savings",
		Type:          models.AccountTypeSavings,
		Currency:      models.CurrencyEGP,
	})

	router, addAuth := testRouter(t, db)
	req := httptest.NewRequest(http.MethodGet, "/transactions/new", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	checks := []string{
		"New Transaction",     // page title
		"Savings",             // account in dropdown
		"Expense",             // type selector
		"Income",              // type selector
		"Save Transaction",    // submit button
		`name="amount"`,       // amount input
		`name="category_id"`,  // category selector
	}
	for _, check := range checks {
		if !strings.Contains(body, check) {
			t.Errorf("expected transaction form to contain %q", check)
		}
	}
}

func TestTransactionCreatePage_Success(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	router, addAuth := testRouter(t, db)

	formData := strings.NewReader("type=expense&amount=500&currency=EGP&account_id=" + acc.ID + "&date=2026-03-06")
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	if !strings.Contains(body, "Transaction saved") {
		t.Error("expected success message")
	}
	if !strings.Contains(body, "9,500.00") {
		t.Errorf("expected new balance 9,500.00 in response, got: %s", body)
	}
}

func TestDashboardPage_WithData(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 100000,
	})

	router, addAuth := testRouter(t, db)
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	checks := []string{
		"Net Worth",           // section header
		"HSBC",                // institution name
		"Checking",            // account name
		"100,000.00",          // balance formatted
	}
	for _, check := range checks {
		if !strings.Contains(body, check) {
			t.Errorf("expected dashboard to contain %q", check)
		}
	}
}

func TestTransactionsPage_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	// Create an institution, account, and a transaction
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	// Create a transaction via the service (to update balance atomically)
	router, addAuth := testRouter(t, db)

	formData := strings.NewReader("type=expense&amount=500&currency=EGP&account_id=" + acc.ID + "&date=2026-03-06&note=Test+expense")
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Now fetch the transactions page
	req = httptest.NewRequest(http.MethodGet, "/transactions", nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	checks := []string{
		"Transactions",      // page title
		"All Accounts",      // filter dropdown
		"All Types",         // type filter
		"Test expense",      // transaction note
		"+ New",             // new transaction button
	}
	for _, check := range checks {
		if !strings.Contains(body, check) {
			t.Errorf("expected transactions page to contain %q", check)
		}
	}
}

func TestTransactionsPage_Empty(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	router, addAuth := testRouter(t, db)
	req := httptest.NewRequest(http.MethodGet, "/transactions", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	if !strings.Contains(w.Body.String(), "No transactions found") {
		t.Error("expected empty state message")
	}
}

func TestTransactionsPage_FilterByType(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Type:           models.AccountTypeSavings,
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})

	router, addAuth := testRouter(t, db)

	// Create an expense
	formData := strings.NewReader("type=expense&amount=100&currency=EGP&account_id=" + acc.ID + "&note=expense+item")
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	// Create an income
	formData = strings.NewReader("type=income&amount=200&currency=EGP&account_id=" + acc.ID + "&note=income+item")
	req = httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	// Filter by expense via the HTMX partial endpoint
	req = httptest.NewRequest(http.MethodGet, "/transactions/list?type=expense", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "expense item") {
		t.Error("expected filtered list to contain 'expense item'")
	}
	if strings.Contains(body, "income item") {
		t.Error("expected filtered list NOT to contain 'income item'")
	}
}

func TestTransactionEditForm_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	router, addAuth := testRouter(t, db)

	// Create a transaction
	formData := strings.NewReader("type=expense&amount=500&currency=EGP&account_id=" + acc.ID + "&note=Test")
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Get a transaction ID from the API
	req = httptest.NewRequest(http.MethodGet, "/api/transactions?limit=1", nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	var txns []models.Transaction
	json.NewDecoder(w.Body).Decode(&txns)
	if len(txns) == 0 {
		t.Fatal("expected at least 1 transaction")
	}
	txID := txns[0].ID

	// Request edit form
	req = httptest.NewRequest(http.MethodGet, "/transactions/edit/"+txID, nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "Save") {
		t.Error("expected edit form to contain Save button")
	}
	if !strings.Contains(body, `name="amount"`) {
		t.Error("expected edit form to contain amount input")
	}
}

func TestTransactionUpdate_ChangesBalance(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	router, addAuth := testRouter(t, db)

	// Create expense of 500 (balance → 9500)
	formData := strings.NewReader("type=expense&amount=500&currency=EGP&account_id=" + acc.ID)
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	// Get the transaction ID
	req = httptest.NewRequest(http.MethodGet, "/api/transactions?limit=1", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	var txns []models.Transaction
	json.NewDecoder(w.Body).Decode(&txns)
	txID := txns[0].ID

	// Update amount from 500 to 800 (additional 300 deduction, balance → 9200)
	formData = strings.NewReader("type=expense&amount=800&currency=EGP&account_id=" + acc.ID + "&date=2026-03-07")
	req = httptest.NewRequest(http.MethodPut, "/transactions/"+txID, formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Verify balance by creating another 1 expense
	formData = strings.NewReader("type=expense&amount=1&currency=EGP&account_id=" + acc.ID)
	req = httptest.NewRequest(http.MethodPost, "/api/transactions", strings.NewReader(`{"type":"expense","amount":1,"currency":"EGP","account_id":"`+acc.ID+`"}`))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	var resp struct{ NewBalance float64 `json:"new_balance"` }
	json.NewDecoder(w.Body).Decode(&resp)
	if resp.NewBalance != 9199 {
		t.Errorf("expected balance 9199 (10000-800-1), got %f", resp.NewBalance)
	}
}

func TestTransactionDelete_FromUI(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	router, addAuth := testRouter(t, db)

	// Create expense
	formData := strings.NewReader("type=expense&amount=2000&currency=EGP&account_id=" + acc.ID)
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	// Get the transaction ID
	req = httptest.NewRequest(http.MethodGet, "/api/transactions?limit=1", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	var txns []models.Transaction
	json.NewDecoder(w.Body).Decode(&txns)
	txID := txns[0].ID

	// Delete via page handler
	req = httptest.NewRequest(http.MethodDelete, "/transactions/"+txID, nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	// Verify balance restored (10000)
	req = httptest.NewRequest(http.MethodPost, "/api/transactions", strings.NewReader(`{"type":"expense","amount":1,"currency":"EGP","account_id":"`+acc.ID+`"}`))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	var resp struct{ NewBalance float64 `json:"new_balance"` }
	json.NewDecoder(w.Body).Decode(&resp)
	if resp.NewBalance != 9999 {
		t.Errorf("expected balance 9999 (10000-1), got %f", resp.NewBalance)
	}
}

func TestTransactionDuplicate_PrefillsForm(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	router, addAuth := testRouter(t, db)

	// Create a transaction with a note
	formData := strings.NewReader("type=expense&amount=750&currency=EGP&account_id=" + acc.ID + "&note=Coffee+beans")
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	// Get the transaction ID
	req = httptest.NewRequest(http.MethodGet, "/api/transactions?limit=1", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	var txns []models.Transaction
	json.NewDecoder(w.Body).Decode(&txns)
	if len(txns) == 0 {
		t.Fatal("expected at least 1 transaction")
	}
	txID := txns[0].ID

	// Duplicate
	req = httptest.NewRequest(http.MethodGet, "/transactions/new?dup="+txID, nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, `value="750"`) {
		t.Error("expected pre-filled amount of 750")
	}
	if !strings.Contains(body, "Coffee beans") {
		t.Error("expected pre-filled note 'Coffee beans'")
	}
	if !strings.Contains(body, "selected") {
		t.Error("expected pre-selected account")
	}
}

func TestAccountDetailPage_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings EGP",
		Currency:       models.CurrencyEGP,
		InitialBalance: 25000,
	})

	router, addAuth := testRouter(t, db)

	// Create a transaction on this account
	formData := strings.NewReader("type=expense&amount=500&currency=EGP&account_id=" + acc.ID + "&note=Test+expense")
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	// Visit account detail
	req = httptest.NewRequest(http.MethodGet, "/accounts/"+acc.ID, nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	checks := []string{
		"Savings EGP",       // account name
		"HSBC",              // institution name
		"24,500.00",         // balance after 500 expense
		"Test expense",      // transaction in history
		"Transaction History",
	}
	for _, check := range checks {
		if !strings.Contains(body, check) {
			t.Errorf("expected account detail to contain %q", check)
		}
	}
}

func TestAccountDetailPage_CreditCard(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	limit := 50000.0
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Credit Card",
		Type:           models.AccountTypeCreditCard,
		Currency:       models.CurrencyEGP,
		InitialBalance: 0,
		CreditLimit:    &limit,
	})

	router, addAuth := testRouter(t, db)

	// Create an expense
	formData := strings.NewReader("type=expense&amount=10000&currency=EGP&account_id=" + acc.ID)
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	req = httptest.NewRequest(http.MethodGet, "/accounts/"+acc.ID, nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "Available Credit") {
		t.Error("expected credit card to show available credit")
	}
	// Available: 50000 - 10000 = 40000
	if !strings.Contains(body, "40,000.00") {
		t.Error("expected available credit of 40,000.00")
	}
}

func TestAccountDetailPage_NotFound(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/accounts/nonexistent-id", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestQuickEntryForm_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID,
		Name:          "Savings",
		Currency:      models.CurrencyEGP,
	})

	router, addAuth := testRouter(t, db)
	req := httptest.NewRequest(http.MethodGet, "/transactions/quick-form", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	checks := []string{
		"Quick Entry",
		"Savings",
		"Expense",
		"Income",
		`name="amount"`,
	}
	for _, check := range checks {
		if !strings.Contains(body, check) {
			t.Errorf("expected quick-entry form to contain %q", check)
		}
	}
}

func TestQuickEntryCreate_Success(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 5000,
	})

	router, addAuth := testRouter(t, db)

	formData := strings.NewReader("type=expense&amount=300&currency=EGP&account_id=" + acc.ID + "&date=2026-03-07")
	req := httptest.NewRequest(http.MethodPost, "/transactions/quick", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	if !strings.Contains(body, "Saved") {
		t.Error("expected success toast with 'Saved'")
	}
	if !strings.Contains(body, "4,700.00") {
		t.Errorf("expected new balance 4,700.00, got: %s", body)
	}
}

func TestQuickEntryCreate_Error(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	router, addAuth := testRouter(t, db)

	// Submit with invalid account_id
	formData := strings.NewReader("type=expense&amount=100&currency=EGP&account_id=nonexistent&date=2026-03-07")
	req := httptest.NewRequest(http.MethodPost, "/transactions/quick", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}

	if !strings.Contains(w.Body.String(), "bg-red-50") {
		t.Error("expected error message in response")
	}
}

func TestPeoplePage_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "persons")

	router, addAuth := testRouter(t, db)

	// Add a person
	formData := strings.NewReader("name=Ahmed")
	req := httptest.NewRequest(http.MethodPost, "/people/add", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	// Visit people page
	req = httptest.NewRequest(http.MethodGet, "/people", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	checks := []string{"People", "Ahmed", "Record Loan", "Settled"}
	for _, check := range checks {
		if !strings.Contains(body, check) {
			t.Errorf("expected people page to contain %q", check)
		}
	}
}

func TestPeoplePage_LoanAndRepay(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "persons")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})

	router, addAuth := testRouter(t, db)

	// Add person
	formData := strings.NewReader("name=Omar")
	req := httptest.NewRequest(http.MethodPost, "/people/add", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	// Get person ID via API
	req = httptest.NewRequest(http.MethodGet, "/api/persons", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	var persons []models.Person
	json.NewDecoder(w.Body).Decode(&persons)
	if len(persons) == 0 {
		t.Fatal("expected at least 1 person")
	}
	personID := persons[0].ID

	// Record loan (I lent 1000)
	formData = strings.NewReader("loan_type=loan_out&amount=1000&account_id=" + acc.ID)
	req = httptest.NewRequest(http.MethodPost, "/people/"+personID+"/loan", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	if !strings.Contains(body, "They owe you") {
		t.Error("expected 'They owe you' after loan out")
	}
}

func TestTemplateFuncs_FormatNumber(t *testing.T) {
	tests := []struct {
		input    float64
		expected string
	}{
		{0, "0.00"},
		{1234.56, "1,234.56"},
		{1234567.89, "1,234,567.89"},
		{-5000, "-5,000.00"},
		{100, "100.00"},
	}
	for _, tt := range tests {
		got := formatNumber(tt.input)
		if got != tt.expected {
			t.Errorf("formatNumber(%f) = %q, want %q", tt.input, got, tt.expected)
		}
	}
}
