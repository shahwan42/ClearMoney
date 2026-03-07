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
