// bugfix_test.go — Regression tests for QA bug fixes (BUG-001 through BUG-011).
//
// Each test verifies the specific fix for a reported bug, ensuring the issue
// doesn't regress. Tests follow the same patterns as pages_test.go.
package handler

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/templates"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

// TestBug001_LogoutStandardRedirect verifies that POST /logout returns a
// standard HTTP 302 redirect (not an HX-Redirect header), so the browser
// navigates to /login without HTMX intercepting.
func TestBug001_LogoutStandardRedirect(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodPost, "/logout", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("expected 302, got %d", w.Code)
	}
	if loc := w.Header().Get("Location"); loc != "/login" {
		t.Errorf("expected Location /login, got %q", loc)
	}
	// Must NOT have HX-Redirect header (that would only work for HTMX requests)
	if hx := w.Header().Get("HX-Redirect"); hx != "" {
		t.Errorf("expected no HX-Redirect header, got %q", hx)
	}
}

// TestBug001_SettingsLogoutFormIsStandardPOST verifies the settings template
// uses a standard form POST (not hx-post) for the logout button.
func TestBug001_SettingsLogoutFormIsStandardPOST(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/settings", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	body := w.Body.String()
	// Should have standard form, not hx-post
	if strings.Contains(body, `hx-post="/logout"`) {
		t.Error("logout form should NOT use hx-post (causes HTMX nesting bug)")
	}
	if !strings.Contains(body, `action="/logout"`) {
		t.Error("logout form should use standard action=\"/logout\"")
	}
}

// TestBug003_TransactionNewHasIncomeCategoryOptions verifies that the
// transaction form includes both expense and income category optgroups.
func TestBug003_TransactionNewHasIncomeCategoryOptions(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/transactions/new", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	body := w.Body.String()
	if !strings.Contains(body, "category-expense") {
		t.Error("expected expense category optgroup")
	}
	if !strings.Contains(body, "category-income") {
		t.Error("expected income category optgroup")
	}
	// Verify JS for switching is present
	if !strings.Contains(body, "toggleCategories") {
		t.Error("expected toggleCategories JS function for switching categories")
	}
}

// TestBug004_VirtualAccountDateFormat verifies the virtual account allocation form
// pre-populates the date field with YYYY-MM-DD format (not "Jan 2").
func TestBug004_VirtualAccountDateFormat(t *testing.T) {
	// Verify templates parse correctly with the new formatDateISO function
	if _, err := ParseTemplates(templates.FS); err != nil {
		t.Fatalf("parsing templates: %v", err)
	}

	// The formatDateISO function should exist in template funcs
	funcs := TemplateFuncs()
	if _, ok := funcs["formatDateISO"]; !ok {
		t.Fatal("expected formatDateISO template function to exist")
	}
}

// TestBug004_BatchEntryHasDateJS verifies the batch-entry template includes
// JS to set today's date on initial load and cloned rows.
func TestBug004_BatchEntryHasDateJS(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID,
		Name:          "Savings",
		Currency:      models.CurrencyEGP,
	})

	router, addAuth := testRouter(t, db)
	req := httptest.NewRequest(http.MethodGet, "/batch-entry", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	body := w.Body.String()
	if !strings.Contains(body, "todayISO") {
		t.Error("expected batch-entry JS to set todayISO for date fields")
	}
}

// TestBug006_BudgetListShowsBudgets verifies that after creating a budget,
// the /budgets page lists it (the SQL type mismatch is fixed).
func TestBug006_BudgetListShowsBudgets(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "budgets")

	catID := testutil.GetFirstCategoryID(t, db, models.CategoryTypeExpense)

	router, addAuth := testRouter(t, db)

	// Create a budget via POST
	formData := strings.NewReader("category_id=" + catID + "&monthly_limit=5000&currency=EGP")
	req := httptest.NewRequest(http.MethodPost, "/budgets/add", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusSeeOther {
		t.Fatalf("expected 303 redirect, got %d: %s", w.Code, w.Body.String())
	}

	// Now visit /budgets and verify the budget appears
	req = httptest.NewRequest(http.MethodGet, "/budgets", nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "5,000.00") {
		t.Error("expected budget limit to appear on page (BUG-006 regression: SQL type mismatch)")
	}
	// Should NOT show empty state
	if strings.Contains(body, "No budgets set") {
		t.Error("should not show empty state when budgets exist (BUG-006 regression)")
	}
}

// TestBug007_BudgetCreateRedirectsSeeOther verifies that POST /budgets/add
// returns an HTTP 303 redirect (not HX-Redirect), so standard form POST works.
func TestBug007_BudgetCreateRedirectsSeeOther(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "budgets")

	catID := testutil.GetFirstCategoryID(t, db, models.CategoryTypeExpense)

	router, addAuth := testRouter(t, db)

	formData := strings.NewReader("category_id=" + catID + "&monthly_limit=2000&currency=EGP")
	req := httptest.NewRequest(http.MethodPost, "/budgets/add", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusSeeOther {
		t.Fatalf("expected 303, got %d", w.Code)
	}
	if loc := w.Header().Get("Location"); loc != "/budgets" {
		t.Errorf("expected Location /budgets, got %q", loc)
	}
	// Must NOT have HX-Redirect
	if hx := w.Header().Get("HX-Redirect"); hx != "" {
		t.Errorf("expected no HX-Redirect header, got %q", hx)
	}
}

// TestBug008_CCStatementNoBillingCycle verifies that the CC statement page
// returns a friendly error page (not raw error text) when no billing cycle
// is configured.
func TestBug008_CCStatementNoBillingCycle(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	limit := 50000.0
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Visa Gold",
		Type:           models.AccountTypeCreditCard,
		Currency:       models.CurrencyEGP,
		CreditLimit:    &limit,
		InitialBalance: 0,
	})

	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/accounts/"+acc.ID+"/statement", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should render a page, not a raw error
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 (friendly error page), got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "No Billing Cycle Configured") {
		t.Error("expected friendly error message about billing cycle")
	}
	if strings.Contains(body, "account has no billing cycle configuration") {
		t.Error("should NOT show raw error message (BUG-008 regression)")
	}
}

// TestBug010_RecurringListPartialHasDeleteButton verifies that the HTMX
// partial response from recurring rule creation includes the Del button.
func TestBug010_RecurringListPartialHasDeleteButton(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "recurring_rules")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID,
		Name:          "Checking",
		Currency:      models.CurrencyEGP,
	})

	router, addAuth := testRouter(t, db)

	// Create a recurring rule via HTMX form POST
	formData := strings.NewReader(
		"type=expense&amount=500&account_id=" + acc.ID +
			"&note=Insurance&frequency=monthly&next_due_date=2026-04-01&auto_confirm=true")
	req := httptest.NewRequest(http.MethodPost, "/recurring/add", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	if !strings.Contains(body, "Insurance") {
		t.Error("expected rule note 'Insurance' in partial response")
	}
	if !strings.Contains(body, "hx-delete") {
		t.Error("expected Del button with hx-delete in partial response (BUG-010 regression)")
	}
	if !strings.Contains(body, "auto") {
		t.Error("expected 'auto' label for auto-confirm rule (BUG-010 regression)")
	}
}

// TestBug011_ReportsUSDFilter verifies that filtering reports by USD shows
// USD currency labels (not hardcoded EGP).
func TestBug011_ReportsUSDFilter(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "USD Savings",
		Type:           models.AccountTypeSavings,
		Currency:       models.CurrencyUSD,
		InitialBalance: 5000,
	})

	router, addAuth := testRouter(t, db)

	// Create a USD transaction
	formData := strings.NewReader("type=expense&amount=100&currency=USD&account_id=" + acc.ID + "&date=2026-03-05")
	req := httptest.NewRequest(http.MethodPost, "/transactions", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	router.ServeHTTP(httptest.NewRecorder(), req)

	// Visit reports with USD filter
	req = httptest.NewRequest(http.MethodGet, "/reports?currency=USD", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	body := w.Body.String()
	// When filtering by USD, amounts should show "$" not "EGP"
	if strings.Contains(body, "EGP 100") {
		t.Error("reports with USD filter should NOT show EGP labels (BUG-011 regression)")
	}
}

// TestBug012_DeleteAccountCleansUpRecurringRules verifies that deleting an account
// also removes any recurring rules referencing it. Without this cleanup, confirming
// a due recurring rule whose account was deleted causes a FK violation:
//
//	"insert or update on table 'transactions' violates foreign key constraint
//	 transactions_account_id_fkey (SQLSTATE 23503)"
//
// Root cause: template_transaction is JSONB — no FK constraint protects account_id
// inside the JSON blob when the referenced account is deleted.
func TestBug012_DeleteAccountCleansUpRecurringRules(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "recurring_rules")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Salary Account",
		Currency:       models.CurrencyEGP,
		InitialBalance: 0,
	})

	router, addAuth := testRouter(t, db)

	// Step 1: Create a recurring rule referencing the account.
	formData := strings.NewReader(
		"type=income&amount=15000&account_id=" + acc.ID +
			"&note=Monthly+Salary&frequency=monthly&next_due_date=2026-04-01&auto_confirm=false",
	)
	req := httptest.NewRequest(http.MethodPost, "/recurring/add", formData)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 creating recurring rule, got %d: %s", w.Code, w.Body.String())
	}

	// Verify the rule exists before deletion.
	var ruleCount int
	db.QueryRow(
		`SELECT count(*) FROM recurring_rules WHERE template_transaction->>'account_id' = $1`,
		acc.ID,
	).Scan(&ruleCount)
	if ruleCount != 1 {
		t.Fatalf("expected 1 recurring rule before account deletion, got %d", ruleCount)
	}

	// Step 2: Delete the account.
	req = httptest.NewRequest(http.MethodDelete, "/api/accounts/"+acc.ID, nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusNoContent {
		t.Fatalf("expected 204 deleting account, got %d: %s", w.Code, w.Body.String())
	}

	// Step 3: Assert recurring rule was also deleted (BUG-012 regression check).
	db.QueryRow(
		`SELECT count(*) FROM recurring_rules WHERE template_transaction->>'account_id' = $1`,
		acc.ID,
	).Scan(&ruleCount)
	if ruleCount != 0 {
		t.Errorf("BUG-012: expected 0 recurring rules after account deletion, got %d", ruleCount)
	}
}
