package handler

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

// TransactionHandler groups HTTP handlers for transaction endpoints.
// Like a Laravel TransactionController — each method handles one route.
type TransactionHandler struct {
	svc *service.TransactionService
}

func NewTransactionHandler(svc *service.TransactionService) *TransactionHandler {
	return &TransactionHandler{svc: svc}
}

// Routes registers transaction routes on the given router.
func (h *TransactionHandler) Routes(r chi.Router) {
	r.Post("/", h.Create)
	r.Get("/", h.List)
	r.Get("/{id}", h.Get)
	r.Delete("/{id}", h.Delete)
}

// createTransactionResponse wraps the created transaction with the updated balance.
// This lets the client update both the transaction list and balance display in one call.
type createTransactionResponse struct {
	Transaction models.Transaction `json:"transaction"`
	NewBalance  float64            `json:"new_balance"`
}

// Create adds a new transaction and atomically updates the account balance.
// POST /api/transactions
func (h *TransactionHandler) Create(w http.ResponseWriter, r *http.Request) {
	var tx models.Transaction
	if err := json.NewDecoder(r.Body).Decode(&tx); err != nil {
		respondError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	created, newBalance, err := h.svc.Create(r.Context(), tx)
	if err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusCreated, createTransactionResponse{
		Transaction: created,
		NewBalance:  newBalance,
	})
}

// List returns recent transactions, optionally filtered by account.
// GET /api/transactions?account_id=xxx&limit=20
func (h *TransactionHandler) List(w http.ResponseWriter, r *http.Request) {
	accountID := r.URL.Query().Get("account_id")
	limit := parseLimit(r.URL.Query().Get("limit"), 15)

	var (
		txns []models.Transaction
		err  error
	)
	if accountID != "" {
		txns, err = h.svc.GetByAccount(r.Context(), accountID, limit)
	} else {
		txns, err = h.svc.GetRecent(r.Context(), limit)
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to list transactions")
		return
	}
	if txns == nil {
		txns = []models.Transaction{}
	}
	respondJSON(w, http.StatusOK, txns)
}

// Get returns a single transaction by ID.
// GET /api/transactions/{id}
func (h *TransactionHandler) Get(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	tx, err := h.svc.GetByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, http.StatusNotFound, "transaction not found")
			return
		}
		respondError(w, http.StatusInternalServerError, "failed to get transaction")
		return
	}
	respondJSON(w, http.StatusOK, tx)
}

// Delete removes a transaction and reverses its balance impact.
// DELETE /api/transactions/{id}
func (h *TransactionHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	if err := h.svc.Delete(r.Context(), id); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, http.StatusNotFound, "transaction not found")
			return
		}
		respondError(w, http.StatusInternalServerError, "failed to delete transaction")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// parseLimit converts a query string limit to an int, with a default fallback.
func parseLimit(s string, defaultVal int) int {
	if s == "" {
		return defaultVal
	}
	n, err := strconv.Atoi(s)
	if err != nil || n <= 0 {
		return defaultVal
	}
	return n
}
