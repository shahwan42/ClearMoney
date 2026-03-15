// pages_test.go — Integration tests for HTML page handlers.
//
// These tests verify that pages render correctly with proper content, active tabs,
// content types, and that HTMX form submissions work end-to-end.
//
// Testing strategies used:
//
//   1. Template-only tests (no database):
//      Parse templates, create PageHandler with nil services, call handler directly.
//      Tests: TestHomePage_Renders, TestHomePage_ContentType, TestHomePage_ActiveTab
//      These verify template parsing and rendering without any database dependency.
//
//   2. Full integration tests (with database):
//      Use testRouter(t, db) to create an authenticated router, then exercise
//      the full stack through to the database.
//      Tests: TestAccountsPage_Renders, TestTransactionCreatePage_Success, etc.
//
//   3. Content assertion pattern:
//      strings.Contains(body, "expected text") checks that rendered HTML contains
//      expected elements. This is like:
//        - Laravel: $response->assertSee('expected text')
//        - Django: self.assertContains(response, 'expected text')
//
//   4. Form submission tests:
//      strings.NewReader("field=value&field2=value2") creates form-encoded bodies.
//      The Content-Type must be "application/x-www-form-urlencoded" for ParseForm() to work.
//
// See institution_test.go and auth_test.go for more testing pattern details.
package handler

import (
	"encoding/json"
	"math"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/templates"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// TestHomePage_Renders verifies the home page renders in no-DB mode (nil services).
// This tests the template parsing and empty-state rendering path.
func TestHomePage_Renders(t *testing.T) {
	tmpl, err := ParseTemplates(templates.FS, time.UTC)
	if err != nil {
		t.Fatalf("parsing templates: %v", err)
	}

	pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
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
		"Welcome to ClearMoney", // dashboard empty state (TASK-081)
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
	tmpl, err := ParseTemplates(templates.FS, time.UTC)
	if err != nil {
		t.Fatalf("parsing templates: %v", err)
	}

	pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	pages.Home(w, req)

	ct := w.Header().Get("Content-Type")
	if !strings.Contains(ct, "text/html") {
		t.Errorf("expected text/html content type, got %q", ct)
	}
}

func TestHomePage_ActiveTab(t *testing.T) {
	tmpl, err := ParseTemplates(templates.FS, time.UTC)
	if err != nil {
		t.Fatalf("parsing templates: %v", err)
	}

	pages := NewPageHandler(tmpl, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	pages.Home(w, req)

	body := w.Body.String()
	// The home tab should have the active color (teal-600)
	if !strings.Contains(body, "text-teal-600") {
		t.Error("expected home tab to be active (text-teal-600)")
	}
}

// TestAccountsPage_Renders uses a real database to verify the accounts page
// renders institution names, account names, and form elements.
func TestAccountsPage_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	// Create an institution with an account
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeCurrent,
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
		"openCreateSheet",     // FAB button to open create sheet
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

// TestTransactionCreatePage_Success tests the HTMX form submission for creating
// a transaction. Verifies the success message and updated balance are in the response.
func TestTransactionCreatePage_Success(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeCurrent,
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
		Type:           models.AccountTypeCurrent,
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
		Type:           models.AccountTypeCurrent,
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

// TestTransactionsPage_FilterByType tests the HTMX partial endpoint for filtering
// transactions by type. Creates both expense and income, then filters to expense-only.
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
		Type:           models.AccountTypeCurrent,
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

// TestTransactionEditForm_ShowsVirtualAccount verifies that the edit form displays
// virtual accounts and pre-selects the one currently allocated to the transaction.
func TestTransactionEditForm_ShowsVirtualAccount(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	testutil.CleanTable(t, db, "virtual_accounts")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeCurrent,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})
	va := testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name:      "Vacation",
		Icon:      "\U0001F3D6",
		AccountID: &acc.ID,
	})

	router, addAuth := testRouter(t, db)

	// Create a transaction and allocate it to the virtual account
	formData := strings.NewReader("type=expense&amount=500&currency=EGP&account_id=" + acc.ID + "&virtual_account_id=" + va.ID)
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

	// Request edit form
	req = httptest.NewRequest(http.MethodGet, "/transactions/edit/"+txID, nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "virtual_account_id") {
		t.Error("expected edit form to contain virtual_account_id select")
	}
	if !strings.Contains(body, "Vacation") {
		t.Error("expected edit form to show Vacation virtual account")
	}
	if !strings.Contains(body, va.ID) {
		t.Error("expected edit form to contain virtual account ID")
	}
}

// TestTransactionUpdate_ChangesBalance verifies that editing a transaction's amount
// correctly adjusts the account balance. The service layer reverses the old amount
// and applies the new one atomically.
func TestTransactionUpdate_ChangesBalance(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeCurrent,
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
		Type:           models.AccountTypeCurrent,
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

// TestTransactionDuplicate_PrefillsForm tests the ?dup= query parameter that
// pre-fills the transaction form from an existing transaction.
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

// TestAccountDetailPage_CreditCard verifies credit-card-specific display:
// available credit = credit_limit - current_balance (which is negative for CC).
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

// TestPeoplePage_LoanAndRepay tests the full loan flow: add person -> record loan ->
// verify "They owe you" message appears in the response.
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
	// After lending 1000 EGP, the person card should show a positive EGP balance
	if !strings.Contains(body, "EGP 1,000") {
		t.Error("expected EGP 1,000 balance after loan out")
	}
}

// TestInstitutionDeleteConfirm_Renders verifies the delete confirmation sheet
// returns the institution name and account count.
func TestInstitutionDeleteConfirm_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID,
		Name:          "Checking",
		Type:          models.AccountTypeCurrent,
		Currency:      models.CurrencyEGP,
	})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID,
		Name:          "Savings",
		Type:          models.AccountTypeSavings,
		Currency:      models.CurrencyEGP,
	})

	router, addAuth := testRouter(t, db)
	req := httptest.NewRequest(http.MethodGet, "/institutions/"+inst.ID+"/delete-confirm", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	checks := []string{
		"HSBC",                // institution name displayed
		"2",                   // account count
		"Delete Institution",  // delete button text
		"delete-confirm-input", // confirmation input field
	}
	for _, check := range checks {
		if !strings.Contains(body, check) {
			t.Errorf("expected delete confirm to contain %q", check)
		}
	}
}

// TestInstitutionDelete_Success verifies deleting an institution removes it and its accounts.
func TestInstitutionDelete_Success(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "TestBank"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID,
		Name:          "TestAccount",
		Type:          models.AccountTypeCurrent,
		Currency:      models.CurrencyEGP,
	})

	router, addAuth := testRouter(t, db)

	// Delete the institution
	req := httptest.NewRequest(http.MethodDelete, "/institutions/"+inst.ID, nil)
	req.Header.Set("HX-Request", "true")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	if !strings.Contains(body, "Institution deleted") {
		t.Error("expected success message")
	}

	// Verify institution is gone via API
	req2 := httptest.NewRequest(http.MethodGet, "/api/institutions/"+inst.ID, nil)
	addAuth(req2)
	w2 := httptest.NewRecorder()
	router.ServeHTTP(w2, req2)

	if w2.Code != http.StatusNotFound {
		t.Errorf("expected 404 after deletion, got %d", w2.Code)
	}
}

// TestInstitutionDelete_NotFound verifies deleting a non-existent institution returns error.
func TestInstitutionDelete_NotFound(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")

	router, addAuth := testRouter(t, db)
	req := httptest.NewRequest(http.MethodDelete, "/institutions/00000000-0000-0000-0000-000000000000", nil)
	req.Header.Set("HX-Request", "true")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// The handler calls institutionSvc.Delete which calls repo.Delete
	// repo.Delete doesn't error on missing rows (just runs DELETE with no match)
	// So we expect 200 with success message even for non-existent IDs
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

// TestTemplateFuncs_FormatNumber is a unit test for the formatNumber helper.
// Uses a table-driven test pattern with a slice of test cases.
func TestTemplateFuncs_FormatNumber(t *testing.T) {
	tests := []struct {
		input    float64
		expected string
	}{
		{0, "0.00"},
		{math.Copysign(0, -1), "0.00"}, // negative zero must display as "0.00", not "-0.00" (BUG-003)
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

func TestTransactionCreate_WithVirtualAccount(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})
	va := testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name:      "Emergency Fund",
		Icon:      "🏦",
		AccountID: &acc.ID,
	})

	router, addAuth := testRouter(t, db)

	formData := strings.NewReader("type=expense&amount=500&currency=EGP&account_id=" + acc.ID +
		"&date=2026-03-15&virtual_account_id=" + va.ID)
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
		t.Error("expected success message in response")
	}

	// Verify allocation was created
	var allocAmount float64
	err := db.QueryRow(`SELECT amount FROM virtual_account_allocations WHERE virtual_account_id = $1`, va.ID).Scan(&allocAmount)
	if err != nil {
		t.Fatalf("expected allocation row: %v", err)
	}
	if allocAmount != -500 {
		t.Errorf("expected allocation amount -500 for expense, got %f", allocAmount)
	}

	// Verify virtual account balance was updated
	var balance float64
	err = db.QueryRow(`SELECT current_balance FROM virtual_accounts WHERE id = $1`, va.ID).Scan(&balance)
	if err != nil {
		t.Fatalf("querying VA balance: %v", err)
	}
	if balance != -500 {
		t.Errorf("expected VA balance -500, got %f", balance)
	}
}

func TestTransactionCreate_WithoutVirtualAccount_NoAllocation(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})
	// Create a VA but don't select it in the form
	testutil.CreateVirtualAccount(t, db, models.VirtualAccount{Name: "Unused Fund"})

	router, addAuth := testRouter(t, db)

	formData := strings.NewReader("type=expense&amount=200&currency=EGP&account_id=" + acc.ID + "&date=2026-03-15")
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Verify no allocation was created
	var count int
	err := db.QueryRow(`SELECT COUNT(*) FROM virtual_account_allocations`).Scan(&count)
	if err != nil {
		t.Fatalf("querying allocations: %v", err)
	}
	if count != 0 {
		t.Errorf("expected 0 allocations when no VA selected, got %d", count)
	}
}

func TestTransactionDelete_RecalculatesVirtualAccountBalance(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})
	va := testutil.CreateVirtualAccount(t, db, models.VirtualAccount{Name: "Travel Fund", AccountID: &acc.ID})

	router, addAuth := testRouter(t, db)

	// Create a transaction with VA allocation
	formData := strings.NewReader("type=expense&amount=300&currency=EGP&account_id=" + acc.ID +
		"&date=2026-03-15&virtual_account_id=" + va.ID)
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("create: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Get the transaction ID from the DB
	var txID string
	err := db.QueryRow(`SELECT id FROM transactions ORDER BY created_at DESC LIMIT 1`).Scan(&txID)
	if err != nil {
		t.Fatalf("getting transaction ID: %v", err)
	}

	// Verify VA balance is -300 before delete
	var balance float64
	err = db.QueryRow(`SELECT current_balance FROM virtual_accounts WHERE id = $1`, va.ID).Scan(&balance)
	if err != nil {
		t.Fatalf("querying VA balance: %v", err)
	}
	if balance != -300 {
		t.Fatalf("expected VA balance -300 before delete, got %f", balance)
	}

	// Delete the transaction
	req = httptest.NewRequest(http.MethodDelete, "/transactions/"+txID, nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("delete: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Verify VA balance is back to 0
	err = db.QueryRow(`SELECT current_balance FROM virtual_accounts WHERE id = $1`, va.ID).Scan(&balance)
	if err != nil {
		t.Fatalf("querying VA balance after delete: %v", err)
	}
	if balance != 0 {
		t.Errorf("expected VA balance 0 after delete, got %f", balance)
	}
}

// TestVirtualAccountDirectAllocate verifies that the allocate endpoint creates
// a direct allocation (no transaction) and updates the VA balance.
func TestVirtualAccountDirectAllocate(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})
	va := testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name:      "Emergency Fund",
		Icon:      "🏦",
		AccountID: &acc.ID,
	})

	router, addAuth := testRouter(t, db)

	// POST a contribution of 1000
	formData := strings.NewReader("type=contribution&amount=1000&note=Initial+allocation")
	req := httptest.NewRequest(http.MethodPost, "/virtual-accounts/"+va.ID+"/allocate", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK && w.Code != http.StatusSeeOther {
		t.Fatalf("expected redirect, got %d: %s", w.Code, w.Body.String())
	}

	// Verify VA balance is 1000
	var balance float64
	err := db.QueryRow(`SELECT current_balance FROM virtual_accounts WHERE id = $1`, va.ID).Scan(&balance)
	if err != nil {
		t.Fatalf("querying VA balance: %v", err)
	}
	if balance != 1000 {
		t.Errorf("expected VA balance 1000, got %f", balance)
	}

	// Verify NO new transaction was created (the core fix)
	var txCount int
	err = db.QueryRow(`SELECT COUNT(*) FROM transactions`).Scan(&txCount)
	if err != nil {
		t.Fatalf("querying transactions: %v", err)
	}
	if txCount != 0 {
		t.Errorf("expected 0 transactions (direct allocation should not create one), got %d", txCount)
	}

	// Verify allocation record exists with NULL transaction_id
	var allocAmount float64
	var txID *string
	err = db.QueryRow(`SELECT amount, transaction_id FROM virtual_account_allocations WHERE virtual_account_id = $1`, va.ID).Scan(&allocAmount, &txID)
	if err != nil {
		t.Fatalf("querying allocation: %v", err)
	}
	if allocAmount != 1000 {
		t.Errorf("expected allocation amount 1000, got %f", allocAmount)
	}
	if txID != nil {
		t.Errorf("expected NULL transaction_id for direct allocation, got %s", *txID)
	}

	// Verify bank account balance is unchanged
	var accBalance float64
	err = db.QueryRow(`SELECT current_balance FROM accounts WHERE id = $1`, acc.ID).Scan(&accBalance)
	if err != nil {
		t.Fatalf("querying account balance: %v", err)
	}
	if accBalance != 50000 {
		t.Errorf("expected account balance unchanged at 50000, got %f", accBalance)
	}
}

// TestVirtualAccountDirectAllocate_Withdrawal verifies withdrawal allocations.
func TestVirtualAccountDirectAllocate_Withdrawal(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})
	va := testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name:           "Emergency Fund",
		CurrentBalance: 5000,
		AccountID:      &acc.ID,
	})

	router, addAuth := testRouter(t, db)

	formData := strings.NewReader("type=withdrawal&amount=2000&note=Withdrawal")
	req := httptest.NewRequest(http.MethodPost, "/virtual-accounts/"+va.ID+"/allocate", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK && w.Code != http.StatusSeeOther {
		t.Fatalf("expected redirect, got %d: %s", w.Code, w.Body.String())
	}

	// Balance should be recalculated from allocations (only the -2000 allocation exists)
	var balance float64
	err := db.QueryRow(`SELECT current_balance FROM virtual_accounts WHERE id = $1`, va.ID).Scan(&balance)
	if err != nil {
		t.Fatalf("querying VA balance: %v", err)
	}
	if balance != -2000 {
		t.Errorf("expected VA balance -2000 (recalculated from allocations), got %f", balance)
	}
}

// TestVirtualAccountCreateWithAccountLink verifies that creating a VA with account_id stores the link.
func TestVirtualAccountCreateWithAccountLink(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	router, addAuth := testRouter(t, db)

	formData := strings.NewReader("name=New+Fund&account_id=" + acc.ID + "&color=%230d9488")
	req := httptest.NewRequest(http.MethodPost, "/virtual-accounts/add", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK && w.Code != http.StatusSeeOther {
		t.Fatalf("expected redirect, got %d: %s", w.Code, w.Body.String())
	}

	// Verify VA was created with account_id
	var accountID *string
	err := db.QueryRow(`SELECT account_id FROM virtual_accounts WHERE name = 'New Fund'`).Scan(&accountID)
	if err != nil {
		t.Fatalf("querying VA: %v", err)
	}
	if accountID == nil || *accountID != acc.ID {
		t.Errorf("expected VA account_id = %s, got %v", acc.ID, accountID)
	}
}

// TestVirtualAccountDetail_OverAllocationWarning verifies the warning when a single
// VA's balance exceeds the linked bank account's balance.
func TestVirtualAccountDetail_OverAllocationWarning(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Currency:       models.CurrencyEGP,
		InitialBalance: 5000,
	})
	va := testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name:      "Vacation",
		AccountID: &acc.ID,
	})

	// Directly set VA balance higher than account balance
	_, err := db.Exec(`INSERT INTO virtual_account_allocations (virtual_account_id, amount, allocated_at) VALUES ($1, 10000, NOW())`, va.ID)
	if err != nil {
		t.Fatalf("inserting allocation: %v", err)
	}
	_, err = db.Exec(`UPDATE virtual_accounts SET current_balance = 10000 WHERE id = $1`, va.ID)
	if err != nil {
		t.Fatalf("updating VA balance: %v", err)
	}

	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/virtual-accounts/"+va.ID, nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "exceeds the linked account balance") {
		t.Error("expected over-allocation warning in response body")
	}
}

// TestVirtualAccountDetail_GroupOverAllocationWarning verifies the warning when the
// sum of all VA balances on the same account exceeds the bank account balance.
func TestVirtualAccountDetail_GroupOverAllocationWarning(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	// Two VAs, each under account balance individually but exceeding it together
	va1 := testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name:      "Fund A",
		AccountID: &acc.ID,
	})
	va2 := testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name:      "Fund B",
		AccountID: &acc.ID,
	})

	// VA1: 6000, VA2: 6000, total 12000 > account 10000
	for _, va := range []models.VirtualAccount{va1, va2} {
		_, err := db.Exec(`INSERT INTO virtual_account_allocations (virtual_account_id, amount, allocated_at) VALUES ($1, 6000, NOW())`, va.ID)
		if err != nil {
			t.Fatalf("inserting allocation: %v", err)
		}
		_, err = db.Exec(`UPDATE virtual_accounts SET current_balance = 6000 WHERE id = $1`, va.ID)
		if err != nil {
			t.Fatalf("updating VA balance: %v", err)
		}
	}

	router, addAuth := testRouter(t, db)

	// View VA1 detail — individual balance (6000) < account (10000), but group total (12000) > account
	req := httptest.NewRequest(http.MethodGet, "/virtual-accounts/"+va1.ID, nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "Total virtual account allocations") {
		t.Error("expected group over-allocation warning in response body")
	}
}

// TestVirtualAccountDetail_NoWarning verifies no warning when VA balance is under account balance.
func TestVirtualAccountDetail_NoWarning(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})
	va := testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name:      "Emergency Fund",
		AccountID: &acc.ID,
	})

	// VA balance 1000 < account balance 50000
	_, err := db.Exec(`INSERT INTO virtual_account_allocations (virtual_account_id, amount, allocated_at) VALUES ($1, 1000, NOW())`, va.ID)
	if err != nil {
		t.Fatalf("inserting allocation: %v", err)
	}
	_, err = db.Exec(`UPDATE virtual_accounts SET current_balance = 1000 WHERE id = $1`, va.ID)
	if err != nil {
		t.Fatalf("updating VA balance: %v", err)
	}

	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/virtual-accounts/"+va.ID, nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if strings.Contains(body, "exceeds the linked account balance") || strings.Contains(body, "Total virtual account allocations") {
		t.Error("expected no over-allocation warning, but found one")
	}
}
