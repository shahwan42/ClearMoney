package handler

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

// PersonHandler groups HTTP handlers for person (people ledger) endpoints.
type PersonHandler struct {
	svc *service.PersonService
}

func NewPersonHandler(svc *service.PersonService) *PersonHandler {
	return &PersonHandler{svc: svc}
}

// Routes registers person routes on the given router.
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
	persons, err := h.svc.GetAll(r.Context())
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
	created, err := h.svc.Create(r.Context(), p)
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
	p, err := h.svc.GetByID(r.Context(), id)
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
	updated, err := h.svc.Update(r.Context(), p)
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
	if err := h.svc.Delete(r.Context(), id); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, r, http.StatusNotFound, "person not found")
			return
		}
		respondError(w, r, http.StatusInternalServerError, "failed to delete person")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

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
	tx, err := h.svc.RecordLoan(r.Context(), personID, req.AccountID, req.Amount, req.Currency, req.Type, req.Note, time.Time{})
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
	tx, err := h.svc.RecordRepayment(r.Context(), personID, req.AccountID, req.Amount, req.Currency, req.Note, time.Time{})
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusCreated, tx)
}
