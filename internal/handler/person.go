// person.go — JSON API handler for person (people ledger) management.
//
// The "people" feature tracks loans and debts between the user and other people.
// Each person has a running balance: positive = they owe you, negative = you owe them.
//
// Beyond standard CRUD, this handler has two specialized endpoints:
//   - POST /api/persons/{id}/loan — Record lending or borrowing money
//   - POST /api/persons/{id}/repayment — Record a debt repayment
//
// These create transactions AND update the person's running balance atomically.
//
// See institution.go for detailed Go/Laravel/Django handler pattern explanations.
package handler

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	authmw "github.com/shahwan42/clearmoney/internal/middleware"
	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/service"
)

// PersonHandler groups HTTP handlers for person (people ledger) endpoints.
// Mounted at /api/persons in router.go.
type PersonHandler struct {
	svc *service.PersonService
}

func NewPersonHandler(svc *service.PersonService) *PersonHandler {
	return &PersonHandler{svc: svc}
}

// Routes registers person routes on the given router.
// Beyond standard REST CRUD, includes /loan and /repayment actions.
func (h *PersonHandler) Routes(r chi.Router) {
	r.Get("/", h.List)
	r.Post("/", h.Create)
	r.Get("/{id}", h.Get)
	r.Put("/{id}", h.Update)
	r.Delete("/{id}", h.Delete)
	r.Post("/{id}/loan", h.RecordLoan)
	r.Post("/{id}/repayment", h.RecordRepayment)
}

// List returns all persons.
// GET /api/persons
func (h *PersonHandler) List(w http.ResponseWriter, r *http.Request) {
	userID := authmw.UserID(r.Context())
	persons, err := h.svc.GetAll(r.Context(), userID)
	if err != nil {
		respondError(w, r, http.StatusInternalServerError, "failed to list persons")
		return
	}
	if persons == nil {
		persons = []models.Person{}
	}
	respondJSON(w, http.StatusOK, persons)
}

// Create adds a new person.
// POST /api/persons
func (h *PersonHandler) Create(w http.ResponseWriter, r *http.Request) {
	var p models.Person
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}
	userID := authmw.UserID(r.Context())
	created, err := h.svc.Create(r.Context(), userID, p)
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusCreated, created)
}

// Get returns a single person.
// GET /api/persons/{id}
func (h *PersonHandler) Get(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	userID := authmw.UserID(r.Context())
	p, err := h.svc.GetByID(r.Context(), userID, id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, r, http.StatusNotFound, "person not found")
			return
		}
		respondError(w, r, http.StatusInternalServerError, "failed to get person")
		return
	}
	respondJSON(w, http.StatusOK, p)
}

// Update modifies a person.
// PUT /api/persons/{id}
func (h *PersonHandler) Update(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	var p models.Person
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}
	p.ID = id
	userID := authmw.UserID(r.Context())
	updated, err := h.svc.Update(r.Context(), userID, p)
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, updated)
}

// Delete removes a person.
// DELETE /api/persons/{id}
func (h *PersonHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	userID := authmw.UserID(r.Context())
	if err := h.svc.Delete(r.Context(), userID, id); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, r, http.StatusNotFound, "person not found")
			return
		}
		respondError(w, r, http.StatusInternalServerError, "failed to delete person")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// loanRequest holds the JSON body for recording a loan.
// loan_out = "I lent money to them" (they owe me)
// loan_in = "I borrowed money from them" (I owe them)
type loanRequest struct {
	AccountID string                 `json:"account_id"`
	Amount    float64                `json:"amount"`
	Currency  models.Currency        `json:"currency"`
	Type      models.TransactionType `json:"type"` // loan_out or loan_in
	Note      *string                `json:"note,omitempty"`
}

// RecordLoan records a loan (lent or borrowed).
// POST /api/persons/{id}/loan
func (h *PersonHandler) RecordLoan(w http.ResponseWriter, r *http.Request) {
	personID := chi.URLParam(r, "id")
	var req loanRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}
	userID := authmw.UserID(r.Context())
	tx, err := h.svc.RecordLoan(r.Context(), userID, personID, req.AccountID, req.Amount, req.Currency, req.Type, req.Note, time.Time{})
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusCreated, tx)
}

type repaymentRequest struct {
	AccountID string          `json:"account_id"`
	Amount    float64         `json:"amount"`
	Currency  models.Currency `json:"currency"`
	Note      *string         `json:"note,omitempty"`
}

// RecordRepayment records a loan repayment.
// POST /api/persons/{id}/repayment
func (h *PersonHandler) RecordRepayment(w http.ResponseWriter, r *http.Request) {
	personID := chi.URLParam(r, "id")
	var req repaymentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}
	userID := authmw.UserID(r.Context())
	tx, err := h.svc.RecordRepayment(r.Context(), userID, personID, req.AccountID, req.Amount, req.Currency, req.Note, time.Time{})
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusCreated, tx)
}
