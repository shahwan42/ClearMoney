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

// InstitutionHandler groups HTTP handlers for institution endpoints.
// It depends on the InstitutionService for business logic.
//
// In Laravel terms, this is a controller class:
//
//	class InstitutionController {
//	    public function __construct(private InstitutionService $service) {}
//	    public function index(Request $request) { ... }
//	}
type InstitutionHandler struct {
	svc *service.InstitutionService
}

// NewInstitutionHandler creates the handler with its service dependency.
func NewInstitutionHandler(svc *service.InstitutionService) *InstitutionHandler {
	return &InstitutionHandler{svc: svc}
}

// Routes registers institution routes on the given router.
// This is like Laravel's Route::resource('institutions', InstitutionController::class).
func (h *InstitutionHandler) Routes(r chi.Router) {
	r.Get("/", h.List)
	r.Post("/", h.Create)
	r.Get("/{id}", h.Get)
	r.Put("/{id}", h.Update)
	r.Delete("/{id}", h.Delete)
}

// List returns all institutions as JSON.
// GET /api/institutions
func (h *InstitutionHandler) List(w http.ResponseWriter, r *http.Request) {
	institutions, err := h.svc.GetAll(r.Context())
	if err != nil {
		respondError(w, r, http.StatusInternalServerError, "failed to list institutions")
		return
	}
	// Return empty array instead of null when no institutions exist
	if institutions == nil {
		institutions = []models.Institution{}
	}
	respondJSON(w, http.StatusOK, institutions)
}

// Create adds a new institution.
// POST /api/institutions
func (h *InstitutionHandler) Create(w http.ResponseWriter, r *http.Request) {
	var inst models.Institution
	if err := json.NewDecoder(r.Body).Decode(&inst); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}

	created, err := h.svc.Create(r.Context(), inst)
	if err != nil {
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusCreated, created)
}

// Get returns a single institution by ID.
// GET /api/institutions/{id}
func (h *InstitutionHandler) Get(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	inst, err := h.svc.GetByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, r, http.StatusNotFound, "institution not found")
			return
		}
		respondError(w, r, http.StatusInternalServerError, "failed to get institution")
		return
	}
	respondJSON(w, http.StatusOK, inst)
}

// Update modifies an existing institution.
// PUT /api/institutions/{id}
func (h *InstitutionHandler) Update(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	var inst models.Institution
	if err := json.NewDecoder(r.Body).Decode(&inst); err != nil {
		respondError(w, r, http.StatusBadRequest, "invalid JSON body")
		return
	}
	inst.ID = id

	updated, err := h.svc.Update(r.Context(), inst)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, r, http.StatusNotFound, "institution not found")
			return
		}
		respondError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, updated)
}

// Delete removes an institution by ID.
// DELETE /api/institutions/{id}
func (h *InstitutionHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	if err := h.svc.Delete(r.Context(), id); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			respondError(w, r, http.StatusNotFound, "institution not found")
			return
		}
		respondError(w, r, http.StatusInternalServerError, "failed to delete institution")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
