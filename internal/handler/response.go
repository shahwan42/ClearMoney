package handler

import (
	"encoding/json"
	"net/http"

	authmw "github.com/ahmedelsamadisi/clearmoney/internal/middleware"
)

// respondJSON writes a JSON response with the given status code.
// This is a helper to avoid repeating Content-Type + Marshal + Write everywhere.
// Similar to Laravel's response()->json($data, $status).
func respondJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// respondError writes a JSON error response and logs it server-side.
// 5xx errors are logged at ERROR level, 4xx at WARN.
// Returns a consistent error format: {"error": "message"}.
func respondError(w http.ResponseWriter, r *http.Request, status int, message string) {
	logger := authmw.Log(r.Context())
	if status >= 500 {
		logger.Error(message, "status", status)
	} else {
		logger.Warn(message, "status", status)
	}
	respondJSON(w, status, map[string]string{"error": message})
}
