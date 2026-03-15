// Rate-limiting middleware using the token bucket algorithm.
//
// # What This Does
//
// Limits the number of requests per IP address to prevent abuse (brute-force
// login attempts, resource exhaustion, etc.). Each IP gets a "bucket" of tokens
// that refills at a steady rate. One token is consumed per request. When the
// bucket is empty, the request gets a 429 Too Many Requests response.
//
// # Laravel/Django Comparison
//
//   - Laravel:  Like Route::middleware('throttle:60,1') or RateLimiter::for()
//     in RouteServiceProvider. Laravel uses Redis/cache to track request counts.
//   - Django:   Like django-ratelimit or DRF's throttle_classes (AnonRateThrottle,
//     UserRateThrottle). Django uses cache backends for storage.
//
// # Token Bucket Algorithm
//
// Instead of counting requests in a sliding window (like Laravel/Django), we use
// a token bucket. Think of it as a bucket that holds tokens:
//   - The bucket starts full (capacity = Burst)
//   - Each request consumes 1 token
//   - Tokens are added back at a steady Rate (tokens per second)
//   - If the bucket is empty, the request is rejected
//
// This naturally allows short bursts of activity while enforcing a long-term rate.
//
// See: https://en.wikipedia.org/wiki/Token_bucket
package middleware

import (
	"fmt"
	"math"
	"net"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/logutil"
)

// RateLimitConfig holds the settings for a rate limiter instance.
// Create different configs for different route groups (login, API, pages).
//
// Laravel analogy: Like defining a named rate limiter in RouteServiceProvider:
//
//	RateLimiter::for('api', function () {
//	    return Limit::perMinute(60);
//	});
type RateLimitConfig struct {
	Rate            float64       // Tokens added per second (e.g., 1.0 = 60/min)
	Burst           int           // Max tokens (bucket capacity) — allows short bursts
	CleanupInterval time.Duration // How often to purge stale entries (e.g., 5 minutes)
	StaleAfter      time.Duration // Remove entries not seen for this long (e.g., 10 minutes)
}

// tokenBucket tracks the token state for a single IP address.
// Like one row in Laravel's cache-based rate limiter store.
type tokenBucket struct {
	tokens     float64   // Current available tokens (fractional — refills continuously)
	lastAccess time.Time // Last time this bucket was checked (for refill calculation + cleanup)
}

// RateLimiter manages per-IP token buckets with automatic cleanup.
// Create one instance per route group (e.g., loginLimiter, apiLimiter).
//
// Thread-safe: all access to the buckets map is protected by a sync.Mutex.
// In Go, a Mutex is like a lock — only one goroutine can hold it at a time.
// This is necessary because HTTP requests are handled concurrently in Go
// (each request runs in its own goroutine).
//
// See: https://pkg.go.dev/sync#Mutex
type RateLimiter struct {
	mu      sync.Mutex
	buckets map[string]*tokenBucket
	config  RateLimitConfig
	stopCh  chan struct{} // Signal to stop the cleanup goroutine
}

// NewRateLimiter creates a rate limiter and starts a background cleanup goroutine.
// The cleanup goroutine runs every config.CleanupInterval and removes IP entries
// that haven't been seen for config.StaleAfter duration. This prevents unbounded
// memory growth from one-time visitors.
//
// Call Stop() when the limiter is no longer needed (typically via defer).
//
// Laravel analogy: Like `new RateLimiter($cache)` — but in-memory instead of Redis.
func NewRateLimiter(config RateLimitConfig) *RateLimiter {
	rl := &RateLimiter{
		buckets: make(map[string]*tokenBucket),
		config:  config,
		stopCh:  make(chan struct{}),
	}
	go rl.cleanupLoop()
	return rl
}

// Allow checks whether the given IP is allowed to make a request.
// Returns true if a token was consumed, false if the bucket is empty (rate limited).
//
// How the refill works:
//  1. Calculate time elapsed since last access
//  2. Add elapsed * rate tokens (capped at burst)
//  3. If tokens >= 1, consume one and allow
//  4. If tokens < 1, deny
func (rl *RateLimiter) Allow(ip string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	b, exists := rl.buckets[ip]
	if !exists {
		// First request from this IP — start with a full bucket minus 1 token.
		rl.buckets[ip] = &tokenBucket{
			tokens:     float64(rl.config.Burst) - 1,
			lastAccess: now,
		}
		return true
	}

	// Refill tokens based on elapsed time.
	elapsed := now.Sub(b.lastAccess).Seconds()
	b.tokens += elapsed * rl.config.Rate
	if b.tokens > float64(rl.config.Burst) {
		b.tokens = float64(rl.config.Burst)
	}
	b.lastAccess = now

	if b.tokens >= 1.0 {
		b.tokens--
		return true
	}

	return false
}

// RetryAfter returns the number of seconds until the next token is available
// for the given IP. Used to set the Retry-After HTTP header on 429 responses.
func (rl *RateLimiter) RetryAfter(ip string) int {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	b, exists := rl.buckets[ip]
	if !exists {
		return 0
	}

	// Tokens needed = 1.0 - current tokens. Time = tokens_needed / rate.
	needed := 1.0 - b.tokens
	if needed <= 0 {
		return 0
	}
	seconds := needed / rl.config.Rate
	return int(math.Ceil(seconds))
}

// Stop terminates the background cleanup goroutine.
// Call this when the rate limiter is no longer needed (via defer in router.go).
func (rl *RateLimiter) Stop() {
	close(rl.stopCh)
}

// cleanupLoop runs periodically to remove stale IP entries.
// This is a goroutine (lightweight thread) — launched by NewRateLimiter.
//
// select{} is Go's way to wait on multiple channels simultaneously.
// Like Python's asyncio.wait() or a Laravel queue worker's sleep loop,
// but more efficient — the goroutine is parked (no CPU) until a signal arrives.
//
// See: https://go.dev/tour/concurrency/5
func (rl *RateLimiter) cleanupLoop() {
	ticker := time.NewTicker(rl.config.CleanupInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			rl.cleanup()
		case <-rl.stopCh:
			return
		}
	}
}

// cleanup removes IP entries that haven't been accessed recently.
func (rl *RateLimiter) cleanup() {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	cutoff := time.Now().Add(-rl.config.StaleAfter)
	for ip, bucket := range rl.buckets {
		if bucket.lastAccess.Before(cutoff) {
			delete(rl.buckets, ip)
		}
	}
}

// RateLimit returns middleware that enforces per-IP rate limiting.
// Follows the same "middleware factory" pattern as Auth() in auth.go:
//
//	r.Use(authmw.RateLimit(limiter))
//
// The outer function captures the limiter via closure, just like Auth()
// captures authSvc. The inner function is the actual middleware.
//
// On rate limit: returns 429 with Retry-After header.
// For HTMX requests (HX-Request: true), returns an HTML error partial
// that matches the existing error styling. For regular requests, returns
// plain text.
func RateLimit(limiter *RateLimiter) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ip := clientIP(r)

			if !limiter.Allow(ip) {
				retryAfter := limiter.RetryAfter(ip)
				w.Header().Set("Retry-After", strconv.Itoa(retryAfter))

				logutil.Log(r.Context()).Warn("rate limit exceeded",
					"ip", ip,
					"retry_after", retryAfter,
				)

				// For HTMX requests, return styled HTML that can be swapped in.
				if r.Header.Get("HX-Request") == "true" {
					w.Header().Set("Content-Type", "text/html; charset=utf-8")
					w.WriteHeader(http.StatusTooManyRequests)
					fmt.Fprintf(w, `<div class="bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 p-3 rounded-lg text-sm">`+
						`<p class="font-medium">Too many requests</p>`+
						`<p class="text-xs mt-1 text-red-600 dark:text-red-400">Please wait %d seconds before trying again.</p>`+
						`</div>`, retryAfter)
					return
				}

				http.Error(w, "Too Many Requests", http.StatusTooManyRequests)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// clientIP extracts the real client IP from the request.
// Checks proxy headers first, falls back to RemoteAddr.
//
// Order: X-Forwarded-For (first IP) → X-Real-IP → RemoteAddr (strip port).
//
// Laravel analogy: Like $request->ip() which checks trusted proxies.
// Django analogy: Like get_client_ip() using META['HTTP_X_FORWARDED_FOR'].
func clientIP(r *http.Request) string {
	// X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
	// The first one is the original client IP.
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		if ip := strings.TrimSpace(strings.SplitN(xff, ",", 2)[0]); ip != "" {
			return ip
		}
	}

	if xri := r.Header.Get("X-Real-IP"); xri != "" {
		return strings.TrimSpace(xri)
	}

	// RemoteAddr is "IP:port" — strip the port.
	// net.SplitHostPort handles IPv4 and IPv6 addresses correctly.
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr // Fallback if parsing fails
	}
	return host
}
