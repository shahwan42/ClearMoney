package handler

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"time"

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
	r.Post("/transfer", h.Transfer)
	r.Post("/exchange", h.Exchange)
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
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}

	created, newBalance, err := h.svc.Create(r.Context(), tx)
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusCreated, createTransactionResponse{
		Transaction: created,
		NewBalance:  newBalance,
	})
}

// transferRequest holds the JSON body for creating a transfer.
type transferRequest struct {
	SourceAccountID string          `json:"source_account_id"`
	DestAccountID   string          `json:"dest_account_id"`
	Amount          float64         `json:"amount"`
	Currency        models.Currency `json:"currency"`
	Note            *string         `json:"note,omitempty"`
	Date            string          `json:"date,omitempty"`
}

// Transfer creates a transfer between two accounts.
// POST /api/transactions/transfer
func (h *TransactionHandler) Transfer(w http.ResponseWriter, r *http.Request) {
	var req transferRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}

	var date time.Time
	if req.Date != "" {
		parsed, err := time.Parse("2006-01-02", req.Date)
		if err == nil {
			date = parsed
		}
	}

	debit, credit, err := h.svc.CreateTransfer(r.Context(), req.SourceAccountID, req.DestAccountID, req.Amount, req.Currency, req.Note, date)
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusCreated, map[string]any{
		"debit":  debit,
		"credit": credit,
	})
}

// exchangeRequest holds the JSON body for creating a currency exchange.
type exchangeRequest struct {
	SourceAccountID string   `json:"source_account_id"`
	DestAccountID   string   `json:"dest_account_id"`
	Amount          *float64 `json:"amount,omitempty"`
	Rate            *float64 `json:"rate,omitempty"`
	CounterAmount   *float64 `json:"counter_amount,omitempty"`
	Note            *string  `json:"note,omitempty"`
	Date            string   `json:"date,omitempty"`
}

// Exchange creates a currency exchange between two accounts.
// POST /api/transactions/exchange
func (h *TransactionHandler) Exchange(w http.ResponseWriter, r *http.Request) {
	var req exchangeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}

	params := service.ExchangeParams{
		SourceAccountID: req.SourceAccountID,
		DestAccountID:   req.DestAccountID,
		Amount:          req.Amount,
		Rate:            req.Rate,
		CounterAmount:   req.CounterAmount,
		Note:            req.Note,
	}
	if req.Date != "" {
		if parsed, err := time.Parse("2006-01-02", req.Date); err == nil {
			params.Date = parsed
		}
	}

	debit, credit, err := h.svc.CreateExchange(r.Context(), params)
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusCreated, map[string]any{
		"debit":  debit,
		"credit": credit,
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
		respondError(w, r, http.StatusInternalServerError, "failed to list transactions")
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
			respondError(w, r, http.StatusNotFound, "transaction not found")
			return
		}
		respondError(w, r, http.StatusInternalServerError, "failed to get transaction")
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
			respondError(w, r, http.StatusNotFound, "transaction not found")
			return
		}
		respondError(w, r, http.StatusInternalServerError, "failed to delete transaction")
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
