// health_test.go — Tests for the health check endpoint.
//
// These tests call the Healthz handler function directly (not through the router).
// This is a unit test — it tests the handler in isolation without middleware.
//
// Direct handler testing vs router testing:
//   - Direct: Healthz(w, req) — tests just the handler function
//   - Router: router.ServeHTTP(w, req) — tests middleware + routing + handler
// Both patterns are common in Go. Direct testing is faster and more isolated.
//
// w.Result() returns an *http.Response from the recorder, which has StatusCode,
// Header, and Body fields — like inspecting the response in Postman or curl.
//
// See: https://pkg.go.dev/net/http/httptest#ResponseRecorder.Result
package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealthz_ReturnsOK(t *testing.T) {
	// Create fake request and response recorder.
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	w := httptest.NewRecorder()

	// Call the handler directly (no router involved).
	Healthz(w, req)

	// w.Result() converts the recorder into an *http.Response.
	resp := w.Result()
	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected status 200, got %d", resp.StatusCode)
	}

	body := w.Body.String()
	if body != "ok" {
		t.Errorf("expected body 'ok', got %q", body)
	}
}

func TestHealthz_ContentType(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	w := httptest.NewRecorder()

	Healthz(w, req)

	// Verify the Content-Type header was set correctly.
	ct := w.Result().Header.Get("Content-Type")
	if ct != "text/plain; charset=utf-8" {
		t.Errorf("expected Content-Type text/plain, got %q", ct)
	}
}
