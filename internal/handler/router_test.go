// Router tests verify that the chi router is wired correctly.
//
// Go HTTP Testing Patterns for Laravel/Django developers:
//
// Go's standard library provides httptest for testing HTTP handlers without starting a real server.
// This is similar to:
//   - Laravel: $this->get('/healthz')->assertStatus(200)
//   - Django: self.client.get('/healthz') using TestCase
//
// Key testing tools:
//
//   httptest.NewRequest(method, url, body):
//     Creates a fake *http.Request without making a network call.
//     Like Laravel's Request::create() or Django's RequestFactory().
//     See: https://pkg.go.dev/net/http/httptest#NewRequest
//
//   httptest.NewRecorder():
//     Creates a fake http.ResponseWriter that captures the response (status, headers, body).
//     Like Laravel's TestResponse or Django's response object from self.client.get().
//     After calling a handler, you inspect w.Code (status), w.Body (response body),
//     and w.Header() (response headers).
//     See: https://pkg.go.dev/net/http/httptest#ResponseRecorder
//
//   router.ServeHTTP(w, req):
//     Dispatches the request through the full router (middleware + routing + handler).
//     This is an integration test — it exercises the same code path as a real HTTP request.
//     In Laravel terms, it's like calling $app->handle($request).
//
// Test naming convention: TestTypeName_MethodOrScenario
// Go tests live in _test.go files in the same package (whitebox testing).
package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/config"
)

func TestNewRouter_HealthzEndpoint(t *testing.T) {
	// Pass nil for db — healthz doesn't need a database.
	// This tests the no-DB mode (early return path in NewRouter).
	r := NewRouter(nil, time.UTC, config.Config{})

	// Create a fake GET /healthz request (no real HTTP connection).
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	// Create a recorder to capture the response.
	w := httptest.NewRecorder()

	// Dispatch through the full router stack (middleware + handler).
	r.ServeHTTP(w, req)

	// Assert on the captured response — like Laravel's assertStatus(200).
	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}
	// w.Body is a *bytes.Buffer containing the response body.
	if w.Body.String() != "ok" {
		t.Errorf("expected body 'ok', got %q", w.Body.String())
	}
}

func TestNewRouter_NotFound(t *testing.T) {
	r := NewRouter(nil, time.UTC, config.Config{})

	// Requesting a non-existent route should return 404.
	// chi automatically handles unmatched routes — no need for a custom 404 handler.
	req := httptest.NewRequest(http.MethodGet, "/nonexistent", nil)
	w := httptest.NewRecorder()

	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected status 404, got %d", w.Code)
	}
}
