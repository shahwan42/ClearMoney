// auth_test.go — Integration tests for the full authentication flow.
//
// These tests cover the complete auth lifecycle:
//   1. First-time setup: /setup page renders, PIN creation, auto-login
//   2. Login: correct PIN redirects to /, wrong PIN shows error
//   3. Protected routes: redirect to /login without auth, accessible with auth
//   4. Logout: clears cookie and redirects to /login
//   5. Health check: accessible without auth
//
// Form submission testing:
//   strings.NewReader("pin=1234&confirm_pin=1234") creates a form-encoded body.
//   The Content-Type header must be set to "application/x-www-form-urlencoded"
//   for r.ParseForm() to work. This is like submitting an HTML <form> with POST.
//
//   In Laravel: $this->post('/setup', ['pin' => '1234', 'confirm_pin' => '1234'])
//   In Django: self.client.post('/setup', {'pin': '1234', 'confirm_pin': '1234'})
//
// Cookie assertions:
//   w.Result().Cookies() returns all Set-Cookie headers from the response.
//   We check for the "clearmoney_session" cookie to verify login worked.
//   MaxAge == -1 means "delete this cookie" (used in logout).
//
// See institution_test.go for general testing pattern explanations.
package handler

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func TestLoginPage_RedirectsToSetupWhenNotConfigured(t *testing.T) {
	db := testutil.NewTestDB(t)
	db.Exec("TRUNCATE TABLE user_config")

	router := NewRouter(db)
	req := httptest.NewRequest(http.MethodGet, "/login", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("expected 302, got %d", w.Code)
	}
	if loc := w.Header().Get("Location"); loc != "/setup" {
		t.Errorf("expected redirect to /setup, got %q", loc)
	}
}

func TestSetupPage_RendersWhenNotConfigured(t *testing.T) {
	db := testutil.NewTestDB(t)
	db.Exec("TRUNCATE TABLE user_config")

	router := NewRouter(db)
	req := httptest.NewRequest(http.MethodGet, "/setup", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	body := w.Body.String()
	if !strings.Contains(body, "PIN") {
		t.Error("expected setup page to mention PIN")
	}
}

func TestSetupPage_RedirectsToLoginWhenAlreadyConfigured(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db) // creates a user_config row

	router := NewRouter(db)
	req := httptest.NewRequest(http.MethodGet, "/setup", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("expected 302, got %d", w.Code)
	}
	if loc := w.Header().Get("Location"); loc != "/login" {
		t.Errorf("expected redirect to /login, got %q", loc)
	}
}

func TestSetupSubmit_CreatesPINAndRedirects(t *testing.T) {
	db := testutil.NewTestDB(t)
	db.Exec("TRUNCATE TABLE user_config")

	router := NewRouter(db)
	form := strings.NewReader("pin=1234&confirm_pin=1234")
	req := httptest.NewRequest(http.MethodPost, "/setup", form)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("expected 302 redirect, got %d: %s", w.Code, w.Body.String())
	}
	if loc := w.Header().Get("Location"); loc != "/" {
		t.Errorf("expected redirect to /, got %q", loc)
	}

	// Should have set a session cookie
	cookies := w.Result().Cookies()
	found := false
	for _, c := range cookies {
		if c.Name == "clearmoney_session" && c.Value != "" {
			found = true
		}
	}
	if !found {
		t.Error("expected session cookie to be set after setup")
	}
}

func TestSetupSubmit_MismatchedPINs(t *testing.T) {
	db := testutil.NewTestDB(t)
	db.Exec("TRUNCATE TABLE user_config")

	router := NewRouter(db)
	form := strings.NewReader("pin=1234&confirm_pin=5678")
	req := httptest.NewRequest(http.MethodPost, "/setup", form)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 (re-render), got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "do not match") {
		t.Error("expected mismatch error message")
	}
}

func TestLoginSubmit_CorrectPIN(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db) // PIN is "1234"

	router := NewRouter(db)
	form := strings.NewReader("pin=1234")
	req := httptest.NewRequest(http.MethodPost, "/login", form)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("expected 302 redirect, got %d", w.Code)
	}
	if loc := w.Header().Get("Location"); loc != "/" {
		t.Errorf("expected redirect to /, got %q", loc)
	}
}

func TestLoginSubmit_WrongPIN(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)

	router := NewRouter(db)
	form := strings.NewReader("pin=9999")
	req := httptest.NewRequest(http.MethodPost, "/login", form)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 (re-render), got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "Invalid PIN") {
		t.Error("expected invalid PIN error message")
	}
}

func TestProtectedRoute_RedirectsWithoutAuth(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)

	router := NewRouter(db)
	req := httptest.NewRequest(http.MethodGet, "/accounts", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("expected 302, got %d", w.Code)
	}
	if loc := w.Header().Get("Location"); loc != "/login" {
		t.Errorf("expected redirect to /login, got %q", loc)
	}
}

func TestProtectedRoute_AccessibleWithAuth(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
}

func TestLogout_ClearsCookieAndRedirects(t *testing.T) {
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
		t.Errorf("expected redirect to /login, got %q", loc)
	}

	// Cookie should be cleared (MaxAge -1)
	for _, c := range w.Result().Cookies() {
		if c.Name == "clearmoney_session" && c.MaxAge == -1 {
			return // pass
		}
	}
	t.Error("expected session cookie to be cleared")
}

func TestHealthz_PublicWithoutAuth(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)

	router := NewRouter(db)
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200 for healthz without auth, got %d", w.Code)
	}
}

// --- Brute-force lockout handler tests ---

// submitLogin is a helper that POSTs a PIN to /login and returns the response.
func submitLogin(t *testing.T, router http.Handler, pin string) *httptest.ResponseRecorder {
	t.Helper()
	form := strings.NewReader("pin=" + pin)
	req := httptest.NewRequest(http.MethodPost, "/login", form)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	return w
}

func TestLoginSubmit_LockoutAfterMultipleFailures(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)
	router := NewRouter(db)

	// 3 free failures
	for i := 0; i < 3; i++ {
		w := submitLogin(t, router, "9999")
		if w.Code != http.StatusOK {
			t.Fatalf("attempt %d: expected 200, got %d", i+1, w.Code)
		}
		if strings.Contains(w.Body.String(), "Too many failed attempts") {
			t.Fatalf("attempt %d: should not show lockout message yet", i+1)
		}
	}

	// 4th failure triggers lockout
	w := submitLogin(t, router, "9999")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	body := w.Body.String()
	if !strings.Contains(body, "Too many failed attempts") {
		t.Error("expected lockout message after 4th failure")
	}
}

func TestLoginSubmit_LockoutBlocksCorrectPIN(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)
	router := NewRouter(db)

	// Trigger lockout
	for i := 0; i < 4; i++ {
		submitLogin(t, router, "9999")
	}

	// Correct PIN should be blocked
	w := submitLogin(t, router, "1234")
	if w.Code == http.StatusFound {
		t.Error("expected lockout to block correct PIN, but got redirect (success)")
	}
	if !strings.Contains(w.Body.String(), "Too many failed attempts") {
		t.Error("expected lockout message even with correct PIN")
	}
}

func TestLoginSubmit_SuccessResetsCounter(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)
	router := NewRouter(db)

	// 2 failures
	submitLogin(t, router, "9999")
	submitLogin(t, router, "9999")

	// Successful login
	w := submitLogin(t, router, "1234")
	if w.Code != http.StatusFound {
		t.Fatalf("expected redirect on success, got %d", w.Code)
	}

	// After reset, 3 more failures should not trigger lockout
	for i := 0; i < 3; i++ {
		w := submitLogin(t, router, "9999")
		if strings.Contains(w.Body.String(), "Too many failed attempts") {
			t.Errorf("attempt %d after reset: should not show lockout", i+1)
		}
	}
}

func TestLoginPage_ShowsLockoutOnGET(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)
	router := NewRouter(db)

	// Trigger lockout via POST
	for i := 0; i < 4; i++ {
		submitLogin(t, router, "9999")
	}

	// GET /login should show the lockout message
	req := httptest.NewRequest(http.MethodGet, "/login", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "Too many failed attempts") {
		t.Error("expected lockout message on GET /login")
	}
}
