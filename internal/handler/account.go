// account.go — JSON API handler for account CRUD operations.
//
// Accounts belong to an institution (bank, fintech) and track balances in a specific
// currency (EGP or USD). Types include checking, savings, credit_card, and prepaid.
//
// This handler follows the same patterns as institution.go — see that file for
// detailed Go/Laravel/Django comparisons of handler structs, JSON decoding, etc.
//
// Query parameter filtering example (List method):
//   r.URL.Query().Get("institution_id") extracts query params from the URL.
//   This is like:
//     - Laravel: $request->query('institution_id')
//     - Django: request.GET.get('institution_id')
//
// See: https://pkg.go.dev/net/url#URL.Query
package handler

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

// AccountHandler groups HTTP handlers for account endpoints.
// Like InstitutionHandler, this is a controller struct with service dependency.
type AccountHandler struct {
	svc *service.AccountService
}

func NewAccountHandler(svc *service.AccountService) *AccountHandler {
	return &AccountHandler{svc: svc}
}

// Routes registers account routes on the given router.
// Mounted at /api/accounts in router.go.
func (h *AccountHandler) Routes(r chi.Router) {
	r.Get("/", h.List)
	r.Post("/", h.Create)
	r.Get("/{id}", h.Get)
	r.Put("/{id}", h.Update)
	r.Delete("/{id}", h.Delete)
}

// List returns all accounts, optionally filtered by institution.
// GET /api/accounts
// GET /api/accounts?institution_id=xxx
//
// r.URL.Query() returns the parsed query string as url.Values (a map[string][]string).
// .Get("key") returns the first value for that key, or "" if not present.
// This is like Laravel's $request->query('institution_id') or Django's request.GET.get().
func (h *AccountHandler) List(w http.ResponseWriter, r *http.Request) {
	// Optional filter by institution_id query param
	institutionID := r.URL.Query().Get("institution_id")

	var (
		accounts []models.Account
		err      error
	)
	if institutionID != "" {
		accounts, err = h.svc.GetByInstitution(r.Context(), institutionID)
	} else {
		accounts, err = h.svc.GetAll(r.Context())
	}
	if err != nil {
		respondError(w, r, http.StatusInternalServerError, "failed to list accounts")
		return
	}
	if accounts == nil {
		accounts = []models.Account{}
	}
	respondJSON(w, http.StatusOK, accounts)
}

// Create adds a new account.
// POST /api/accounts
func (h *AccountHandler) Create(w http.ResponseWriter, r *http.Request) {
	var acc models.Account
	if err := json.NewDecoder(r.Body).Decode(&acc); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}

	created, err := h.svc.Create(r.Context(), acc)
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusCreated, created)
}

// Get returns a single account by ID.
// GET /api/accounts/{id}
func (h *AccountHandler) Get(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	acc, err := h.svc.GetByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, r, http.StatusNotFound, "account not found")
			return
		}
		respondError(w, r, http.StatusInternalServerError, "failed to get account")
		return
	}
	respondJSON(w, http.StatusOK, acc)
}

// Update modifies an existing account.
// PUT /api/accounts/{id}
func (h *AccountHandler) Update(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	var acc models.Account
	if err := json.NewDecoder(r.Body).Decode(&acc); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}
	acc.ID = id

	updated, err := h.svc.Update(r.Context(), acc)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, r, http.StatusNotFound, "account not found")
			return
		}
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, updated)
}

// Delete removes an account by ID.
// DELETE /api/accounts/{id}
func (h *AccountHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	if err := h.svc.Delete(r.Context(), id); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, r, http.StatusNotFound, "account not found")
			return
		}
		respondError(w, r, http.StatusInternalServerError, "failed to delete account")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
