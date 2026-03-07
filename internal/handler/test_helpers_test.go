package handler

import (
	"database/sql"
	"net/http"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

// testRouter creates a router with auth pre-configured.
// Returns the router and a function that adds auth cookies to requests.
func testRouter(t *testing.T, db *sql.DB) (*chi.Mux, func(req *http.Request)) {
	t.Helper()
	cookie := testutil.SetupAuth(t, db)
	router := NewRouter(db)
	addAuth := func(req *http.Request) {
		req.AddCookie(cookie)
	}
	return router, addAuth
}
