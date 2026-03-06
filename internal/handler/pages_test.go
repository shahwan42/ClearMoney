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

func TestHomePage_Renders(t *testing.T) {
	tmpl, err := ParseTemplates(templates.FS)
	if err != nil {
		t.Fatalf("parsing templates: %v", err)
	}

	pages := NewPageHandler(tmpl, nil, nil)
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	pages.Home(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()

	// Verify key layout elements are present
	checks := []string{
		"ClearMoney",          // header
		"tailwindcss",         // Tailwind CDN
		"htmx.org",            // HTMX script
		"Net Worth",           // dashboard section
		"Recent Transactions", // transactions section
		"/static/css/app.css", // custom CSS link
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

	pages := NewPageHandler(tmpl, nil, nil)
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

	pages := NewPageHandler(tmpl, nil, nil)
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

	router := NewRouter(db)
	req := httptest.NewRequest(http.MethodGet, "/accounts", nil)
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

	router := NewRouter(db)
	req := httptest.NewRequest(http.MethodGet, "/accounts", nil)
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
