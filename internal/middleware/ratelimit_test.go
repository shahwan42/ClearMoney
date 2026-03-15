package middleware

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// testConfig returns a rate limiter config suitable for tests.
// Very slow refill (1 token per 10 seconds) so tests can exhaust the bucket
// without worrying about refill timing.
func testConfig(burst int) RateLimitConfig {
	return RateLimitConfig{
		Rate:            0.1,          // 1 token per 10 seconds (slow, predictable)
		Burst:           burst,        // configurable per test
		CleanupInterval: time.Hour,    // won't trigger during tests
		StaleAfter:      time.Hour,    // won't trigger during tests
	}
}

// okHandler is a simple handler that returns 200 OK.
var okHandler = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
})

func TestRateLimiter_AllowWithinLimit(t *testing.T) {
	limiter := NewRateLimiter(testConfig(5))
	defer limiter.Stop()

	// All 5 requests within burst should be allowed.
	for i := range 5 {
		if !limiter.Allow("192.168.1.1") {
			t.Errorf("request %d: expected allowed, got blocked", i+1)
		}
	}
}

func TestRateLimiter_BlockAfterBurst(t *testing.T) {
	limiter := NewRateLimiter(testConfig(3))
	defer limiter.Stop()

	// Exhaust the burst.
	for i := range 3 {
		if !limiter.Allow("10.0.0.1") {
			t.Fatalf("request %d should be allowed", i+1)
		}
	}

	// Next request should be blocked.
	if limiter.Allow("10.0.0.1") {
		t.Error("expected request to be blocked after burst exhausted")
	}
}

func TestRateLimiter_TokenRefill(t *testing.T) {
	// Rate: 100 tokens/sec so refill is fast in tests.
	cfg := RateLimitConfig{
		Rate:            100.0,
		Burst:           1,
		CleanupInterval: time.Hour,
		StaleAfter:      time.Hour,
	}
	limiter := NewRateLimiter(cfg)
	defer limiter.Stop()

	// Use the one token.
	if !limiter.Allow("10.0.0.1") {
		t.Fatal("first request should be allowed")
	}

	// Immediately blocked.
	if limiter.Allow("10.0.0.1") {
		t.Fatal("should be blocked immediately after burst")
	}

	// Wait for refill (at 100 tokens/sec, 20ms is 2 tokens).
	time.Sleep(20 * time.Millisecond)

	if !limiter.Allow("10.0.0.1") {
		t.Error("should be allowed after token refill")
	}
}

func TestRateLimiter_DifferentIPs(t *testing.T) {
	limiter := NewRateLimiter(testConfig(1))
	defer limiter.Stop()

	// First IP uses its token.
	if !limiter.Allow("10.0.0.1") {
		t.Fatal("IP 1 first request should be allowed")
	}
	if limiter.Allow("10.0.0.1") {
		t.Fatal("IP 1 should be blocked")
	}

	// Second IP should still have its own token.
	if !limiter.Allow("10.0.0.2") {
		t.Error("IP 2 should be allowed — independent bucket")
	}
}

func TestRateLimiter_RetryAfter(t *testing.T) {
	// Rate: 1 token per second → should need ~1 second to refill.
	cfg := RateLimitConfig{
		Rate:            1.0,
		Burst:           1,
		CleanupInterval: time.Hour,
		StaleAfter:      time.Hour,
	}
	limiter := NewRateLimiter(cfg)
	defer limiter.Stop()

	// Exhaust.
	limiter.Allow("10.0.0.1")

	retryAfter := limiter.RetryAfter("10.0.0.1")
	if retryAfter != 1 {
		t.Errorf("expected RetryAfter=1, got %d", retryAfter)
	}
}

func TestRateLimiter_RetryAfter_UnknownIP(t *testing.T) {
	limiter := NewRateLimiter(testConfig(5))
	defer limiter.Stop()

	if retryAfter := limiter.RetryAfter("unknown"); retryAfter != 0 {
		t.Errorf("expected RetryAfter=0 for unknown IP, got %d", retryAfter)
	}
}

func TestRateLimiter_Cleanup(t *testing.T) {
	cfg := RateLimitConfig{
		Rate:            1.0,
		Burst:           5,
		CleanupInterval: time.Hour,
		StaleAfter:      10 * time.Millisecond, // Expire quickly for test
	}
	limiter := NewRateLimiter(cfg)
	defer limiter.Stop()

	// Add an entry.
	limiter.Allow("10.0.0.1")

	// Verify it exists.
	limiter.mu.Lock()
	if _, exists := limiter.buckets["10.0.0.1"]; !exists {
		limiter.mu.Unlock()
		t.Fatal("bucket should exist")
	}
	limiter.mu.Unlock()

	// Wait for it to become stale, then trigger cleanup.
	time.Sleep(20 * time.Millisecond)
	limiter.cleanup()

	// Verify it was removed.
	limiter.mu.Lock()
	defer limiter.mu.Unlock()
	if _, exists := limiter.buckets["10.0.0.1"]; exists {
		t.Error("stale bucket should have been cleaned up")
	}
}

// --- Middleware integration tests ---

func TestRateLimit_MiddlewareAllows(t *testing.T) {
	limiter := NewRateLimiter(testConfig(5))
	defer limiter.Stop()

	handler := RateLimit(limiter)(okHandler)

	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.RemoteAddr = "192.168.1.1:12345"
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
}

func TestRateLimit_MiddlewareBlocks(t *testing.T) {
	limiter := NewRateLimiter(testConfig(2))
	defer limiter.Stop()

	handler := RateLimit(limiter)(okHandler)

	// Exhaust burst.
	for range 2 {
		req := httptest.NewRequest(http.MethodGet, "/test", nil)
		req.RemoteAddr = "192.168.1.1:12345"
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, req)
	}

	// This one should be blocked.
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.RemoteAddr = "192.168.1.1:12345"
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusTooManyRequests {
		t.Errorf("expected 429, got %d", w.Code)
	}
	if w.Header().Get("Retry-After") == "" {
		t.Error("expected Retry-After header")
	}
	if !strings.Contains(w.Body.String(), "Too Many Requests") {
		t.Error("expected 'Too Many Requests' in response body")
	}
}

func TestRateLimit_HTMXResponse(t *testing.T) {
	limiter := NewRateLimiter(testConfig(1))
	defer limiter.Stop()

	handler := RateLimit(limiter)(okHandler)

	// Exhaust.
	req := httptest.NewRequest(http.MethodGet, "/test", nil)
	req.RemoteAddr = "10.0.0.1:1234"
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	// Block with HTMX header.
	req = httptest.NewRequest(http.MethodGet, "/test", nil)
	req.RemoteAddr = "10.0.0.1:1234"
	req.Header.Set("HX-Request", "true")
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusTooManyRequests {
		t.Errorf("expected 429, got %d", w.Code)
	}
	ct := w.Header().Get("Content-Type")
	if !strings.Contains(ct, "text/html") {
		t.Errorf("expected text/html content type for HTMX, got %s", ct)
	}
	body := w.Body.String()
	if !strings.Contains(body, "Too many requests") {
		t.Error("expected HTML error message in body")
	}
	if !strings.Contains(body, "bg-red-50") {
		t.Error("expected Tailwind error styling in HTML response")
	}
}

func TestClientIP_XForwardedFor(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.Header.Set("X-Forwarded-For", "203.0.113.50, 70.41.3.18, 150.172.238.178")
	req.RemoteAddr = "127.0.0.1:8080"

	ip := clientIP(req)
	if ip != "203.0.113.50" {
		t.Errorf("expected first XFF IP '203.0.113.50', got '%s'", ip)
	}
}

func TestClientIP_XRealIP(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.Header.Set("X-Real-IP", "203.0.113.99")
	req.RemoteAddr = "127.0.0.1:8080"

	ip := clientIP(req)
	if ip != "203.0.113.99" {
		t.Errorf("expected X-Real-IP '203.0.113.99', got '%s'", ip)
	}
}

func TestClientIP_RemoteAddr(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "192.168.1.100:54321"

	ip := clientIP(req)
	if ip != "192.168.1.100" {
		t.Errorf("expected '192.168.1.100' from RemoteAddr, got '%s'", ip)
	}
}

func TestClientIP_RemoteAddrNoPort(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "192.168.1.100" // No port — fallback

	ip := clientIP(req)
	if ip != "192.168.1.100" {
		t.Errorf("expected '192.168.1.100', got '%s'", ip)
	}
}
