// auth_test.go — Integration tests for the magic link authentication flow.
//
// These tests cover the complete auth lifecycle:
//   1. Login page renders correctly
//   2. Login form submission shows "check email" page (always, even for unknown emails)
//   3. Register page renders correctly
//   4. Protected routes redirect to /login without auth
//   5. Protected routes accessible with auth
//   6. Logout clears cookie and redirects
//   7. Health check accessible without auth
//
// See institution_test.go for general testing pattern explanations.
package handler

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/config"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

func TestLoginPage_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)

	router := NewRouter(db, time.UTC, config.Config{})
	req := httptest.NewRequest(http.MethodGet, "/login", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	body := w.Body.String()
	if !strings.Contains(body, "email") {
		t.Error("expected login page to contain email field")
	}
}

func TestLoginSubmit_ShowsCheckEmail(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)

	router := NewRouter(db, time.UTC, config.Config{})
	// Submit with a render time > 2 seconds ago to pass timing check
	rt := time.Now().Unix() - 5
	form := strings.NewReader(fmt.Sprintf("email=test@example.com&_rt=%d", rt))
	req := httptest.NewRequest(http.MethodPost, "/login", form)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	body := w.Body.String()
	if !strings.Contains(body, "Check your email") {
		t.Error("expected 'Check your email' page")
	}
}

func TestRegisterPage_Renders(t *testing.T) {
	db := testutil.NewTestDB(t)

	router := NewRouter(db, time.UTC, config.Config{})
	req := httptest.NewRequest(http.MethodGet, "/register", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	body := w.Body.String()
	if !strings.Contains(body, "Create") {
		t.Error("expected register page to contain 'Create'")
	}
}

func TestProtectedRoute_RedirectsWithoutAuth(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.SetupAuth(t, db)

	router := NewRouter(db, time.UTC, config.Config{})
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
	router, addAuth, _ := testRouter(t, db)

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
	router, addAuth, _ := testRouter(t, db)

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

	router := NewRouter(db, time.UTC, config.Config{})
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200 for healthz without auth, got %d", w.Code)
	}
}
