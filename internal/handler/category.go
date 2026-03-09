package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

// CategoryHandler groups HTTP handlers for category endpoints.
type CategoryHandler struct {
	svc *service.CategoryService
}

func NewCategoryHandler(svc *service.CategoryService) *CategoryHandler {
	return &CategoryHandler{svc: svc}
}

func (h *CategoryHandler) Routes(r chi.Router) {
	r.Get("/", h.List)
	r.Post("/", h.Create)
	r.Put("/{id}", h.Update)
	r.Delete("/{id}", h.Archive) // soft delete
}

// List returns all categories, optionally filtered by ?type=expense|income.
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
