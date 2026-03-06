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
type AccountHandler struct {
	svc *service.AccountService
}

func NewAccountHandler(svc *service.AccountService) *AccountHandler {
	return &AccountHandler{svc: svc}
}

// Routes registers account routes on the given router.
func (h *AccountHandler) Routes(r chi.Router) {
	r.Get("/", h.List)
	r.Post("/", h.Create)
	r.Get("/{id}", h.Get)
	r.Put("/{id}", h.Update)
	r.Delete("/{id}", h.Delete)
}

// List returns all accounts.
// GET /api/accounts
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
		respondError(w, http.StatusInternalServerError, "failed to list accounts")
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
		respondError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	created, err := h.svc.Create(r.Context(), acc)
	if err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
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
			respondError(w, http.StatusNotFound, "account not found")
			return
		}
		respondError(w, http.StatusInternalServerError, "failed to get account")
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
		respondError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	acc.ID = id

	updated, err := h.svc.Update(r.Context(), acc)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, http.StatusNotFound, "account not found")
			return
		}
		respondError(w, http.StatusBadRequest, err.Error())
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
			respondError(w, http.StatusNotFound, "account not found")
			return
		}
		respondError(w, http.StatusInternalServerError, "failed to delete account")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
