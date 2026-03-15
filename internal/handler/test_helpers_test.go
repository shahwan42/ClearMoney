// test_helpers_test.go — Shared test utilities for handler integration tests.
//
// This file provides helper functions used across all handler test files.
// In Go, test helpers are typically placed in a *_test.go file in the same package
// so they're only compiled during testing (not included in production builds).
//
// Go test helper conventions:
//   - t.Helper() marks a function as a test helper, so error stack traces
//     point to the calling test, not to the helper function itself.
//     Like PHPUnit's $this->addToAssertionCount() but for stack traces.
//
//   - Returning closures: testRouter returns an addAuth function (closure)
//     that captures the session cookie. This avoids global state and makes
//     each test's auth setup explicit.
//
// See: https://pkg.go.dev/testing#T.Helper
package handler

import (
	"database/sql"
	"net/http"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/shahwan42/clearmoney/internal/testutil"
)

// testRouter creates a fully-wired router with auth pre-configured for testing.
// Returns the router and an addAuth function that adds the session cookie to requests.
//
// Usage in tests:
//   router, addAuth := testRouter(t, db)
//   req := httptest.NewRequest(http.MethodGet, "/accounts", nil)
//   addAuth(req)  // adds the clearmoney_session cookie
//   w := httptest.NewRecorder()
//   router.ServeHTTP(w, req)
//
// This pattern is similar to:
//   - Laravel: $this->actingAs($user)->get('/accounts')
//   - Django: self.client.login(username='test', password='test')
//
// The addAuth function is a closure — it captures the session cookie from
// testutil.SetupAuth and adds it to any request. Closures in Go work like
// PHP's use() keyword in anonymous functions, or Python's closures.
func testRouter(t *testing.T, db *sql.DB) (*chi.Mux, func(req *http.Request)) {
	t.Helper()
	// SetupAuth creates a user_config row with PIN "1234" and returns the session cookie.
	cookie := testutil.SetupAuth(t, db)
	router := NewRouter(db, time.UTC)
	addAuth := func(req *http.Request) {
		req.AddCookie(cookie)
	}
	return router, addAuth
}
