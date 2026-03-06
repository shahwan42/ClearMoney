package handler

import (
	"encoding/json"
	"net/http"
)

// respondJSON writes a JSON response with the given status code.
// This is a helper to avoid repeating Content-Type + Marshal + Write everywhere.
// Similar to Laravel's response()->json($data, $status).
func respondJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// respondError writes a JSON error response.
// Returns a consistent error format: {"error": "message"}.
func respondError(w http.ResponseWriter, status int, message string) {
	respondJSON(w, status, map[string]string{"error": message})
}
