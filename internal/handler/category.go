// category.go — JSON API handler for transaction category management.
//
// Categories classify transactions (e.g., "Groceries", "Salary", "Fees & Charges").
// There are two types: system categories (seeded, cannot be modified) and custom
// categories (user-created, can be updated/archived).
//
// The DELETE endpoint performs a soft delete (archive) rather than a hard delete,
// preserving data integrity for existing transactions that reference the category.
// This is like Laravel's SoftDeletes trait or Django's is_active flag pattern.
//
// See institution.go for detailed Go/Laravel/Django handler pattern explanations.
package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

// CategoryHandler groups HTTP handlers for category endpoints.
// Mounted at /api/categories in router.go.
type CategoryHandler struct {
	svc *service.CategoryService
}

func NewCategoryHandler(svc *service.CategoryService) *CategoryHandler {
	return &CategoryHandler{svc: svc}
}

// Routes registers category routes.
// Note: DELETE maps to Archive (soft delete), not a hard delete.
func (h *CategoryHandler) Routes(r chi.Router) {
	r.Get("/", h.List)
	r.Post("/", h.Create)
	r.Put("/{id}", h.Update)
	r.Delete("/{id}", h.Archive) // soft delete — sets archived_at, does not remove row
}

// List returns all categories, optionally filtered by ?type=expense|income.
// GET /api/categories
// GET /api/categories?type=expense
//
// The type filter uses models.CategoryType (a string alias) for type safety.
// In Go, you can define named types from primitives:
//   type CategoryType string
// This gives compile-time type checking while still being a string underneath.
func (h *CategoryHandler) List(w http.ResponseWriter, r *http.Request) {
	catType := r.URL.Query().Get("type")

	var (
		categories []models.Category
		err        error
	)
	if catType != "" {
		categories, err = h.svc.GetByType(r.Context(), models.CategoryType(catType))
	} else {
		categories, err = h.svc.GetAll(r.Context())
	}
	if err != nil {
		respondError(w, r, http.StatusInternalServerError, "failed to list categories")
		return
	}
	if categories == nil {
		categories = []models.Category{}
	}
	respondJSON(w, http.StatusOK, categories)
}

// Create adds a new custom category.
func (h *CategoryHandler) Create(w http.ResponseWriter, r *http.Request) {
	var cat models.Category
	if err := json.NewDecoder(r.Body).Decode(&cat); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}
	created, err := h.svc.Create(r.Context(), cat)
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusCreated, created)
}

// Update modifies a custom category.
func (h *CategoryHandler) Update(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	var cat models.Category
	if err := json.NewDecoder(r.Body).Decode(&cat); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}
	cat.ID = id

	updated, err := h.svc.Update(r.Context(), cat)
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, updated)
}

// Archive soft-deletes a custom category.
func (h *CategoryHandler) Archive(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if err := h.svc.Archive(r.Context(), id); err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
