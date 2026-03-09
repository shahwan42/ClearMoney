// response.go — Shared HTTP response helpers for JSON API endpoints.
//
// These are the Go equivalent of:
//   - Laravel: response()->json($data, $status) and abort(404, 'not found')
//   - Django: JsonResponse(data, status=200) and HttpResponseBadRequest
//
// In Go, you write responses by calling methods on http.ResponseWriter (w):
//   1. w.Header().Set(...) — set response headers (must be called before WriteHeader)
//   2. w.WriteHeader(status) — set the HTTP status code (can only be called once)
//   3. w.Write([]byte) or json.NewEncoder(w).Encode(data) — write the body
//
// IMPORTANT: Header order matters in Go. You must set headers BEFORE calling
// WriteHeader(), and you must call WriteHeader() BEFORE writing the body.
// If you call w.Write() without WriteHeader(), Go automatically sends 200.
//
// See: https://pkg.go.dev/net/http#ResponseWriter
// See: https://pkg.go.dev/encoding/json#NewEncoder
package handler

import (
	"encoding/json"
	"net/http"

	authmw "github.com/ahmedelsamadisi/clearmoney/internal/middleware"
)

// respondJSON writes a JSON response with the given status code.
// This is a helper to avoid repeating Content-Type + Marshal + Write everywhere.
//
// Similar to:
//   - Laravel: return response()->json($data, $status);
//   - Django: return JsonResponse(data, status=status)
//
// Uses json.NewEncoder(w).Encode(data) which streams JSON directly to the
// ResponseWriter — more memory-efficient than json.Marshal + w.Write for large responses.
// The `any` type (alias for `interface{}`) accepts any Go value, like PHP's mixed
// or Python's Any. The encoder converts it to JSON using struct tags (e.g., `json:"name"`).
func respondJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// respondError writes a JSON error response and logs it server-side.
// 5xx errors are logged at ERROR level, 4xx at WARN.
// Returns a consistent error format: {"error": "message"}.
//
// Similar to:
//   - Laravel: abort($status, $message) with JSON response
//   - Django: raise Http404("message") but for all error codes
//
// The structured logger is extracted from the request context — it was placed there
// by the RequestLogger middleware, carrying the request ID for log correlation.
func respondError(w http.ResponseWriter, r *http.Request, status int, message string) {
	logger := authmw.Log(r.Context())
	if status >= 500 {
		logger.Error(message, "status", status)
	} else {
		logger.Warn(message, "status", status)
	}
	respondJSON(w, status, map[string]string{"error": message})
}
