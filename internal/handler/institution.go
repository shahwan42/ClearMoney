// institution.go — JSON API handler for institution CRUD operations.
//
// This is a REST API controller for managing financial institutions (banks, fintechs).
// It returns JSON responses and is mounted at /api/institutions in router.go.
//
// Architecture comparison:
//   - Laravel: class InstitutionController extends Controller { index(), store(), show(), update(), destroy() }
//   - Django: class InstitutionViewSet(ModelViewSet): serializer_class = InstitutionSerializer
//   - Go: struct InstitutionHandler with method receivers for each action
//
// In Go, there are no base controller classes to extend. Each handler struct holds
// its dependencies (services) as fields, and methods implement the handler logic.
// This is composition over inheritance — a core Go design principle.
//
// JSON request/response flow:
//   1. Client sends JSON body (POST/PUT) or query params (GET)
//   2. Handler decodes JSON with json.NewDecoder(r.Body).Decode(&target)
//   3. Handler calls service layer for business logic
//   4. Handler writes JSON response with respondJSON(w, status, data)
//
// See: https://pkg.go.dev/encoding/json#NewDecoder (JSON decoding)
// See: https://github.com/go-chi/chi (URL parameter extraction)
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
// In Go, handler structs are the equivalent of controller classes:
//
//   Laravel:                                    Go:
//   class InstitutionController {               type InstitutionHandler struct {
//       private InstitutionService $service;         svc *service.InstitutionService
//       public function __construct(...)         }
//       public function index(Request $req)     func (h *InstitutionHandler) List(w, r)
//       public function store(Request $req)     func (h *InstitutionHandler) Create(w, r)
//   }                                           }
//
// The (h *InstitutionHandler) before the method name is a "method receiver" —
// it attaches the method to the struct, like $this in PHP or self in Python.
// The * means it's a pointer receiver (the handler is not copied per call).
type InstitutionHandler struct {
	svc *service.InstitutionService
}

// NewInstitutionHandler creates the handler with its service dependency.
// This is Go's constructor pattern — there are no __construct() or __init__() methods.
// Instead, you write a New* function that returns a configured struct.
func NewInstitutionHandler(svc *service.InstitutionService) *InstitutionHandler {
	return &InstitutionHandler{svc: svc}
}

// Routes registers institution routes on the given router.
// This is like:
//   - Laravel: Route::resource('institutions', InstitutionController::class)
//   - Django: router.register('institutions', InstitutionViewSet)
//
// The chi.Router parameter is a sub-router already mounted at /api/institutions
// (see router.go), so r.Get("/") here maps to GET /api/institutions.
func (h *InstitutionHandler) Routes(r chi.Router) {
	r.Get("/", h.List)
	r.Post("/", h.Create)
	r.Get("/{id}", h.Get)
	r.Put("/{id}", h.Update)
	r.Delete("/{id}", h.Delete)
}

// List returns all institutions as JSON.
// GET /api/institutions
//
// Like Laravel's InstitutionController@index or Django's list() action.
// Returns [] (empty array) instead of null when no institutions exist —
// this is a JSON best practice so clients don't need null checks.
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
//
// Like Laravel's InstitutionController@store or Django's create() action.
//
// json.NewDecoder(r.Body).Decode(&inst) reads the request body as JSON and
// populates the struct. This is like:
//   - Laravel: $request->validate(['name' => 'required']) then new Institution($request->all())
//   - Django: serializer = InstitutionSerializer(data=request.data); serializer.is_valid()
//
// If the JSON is malformed, Decode returns an error and we respond with 400.
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
//
// chi.URLParam(r, "id") extracts the {id} from the URL path.
// This is like:
//   - Laravel: $request->route('id') or Route::get('/{id}', ...) with route model binding
//   - Django: def retrieve(self, request, pk=None)
//
// Error handling pattern: errors.Is(err, sql.ErrNoRows) checks if the error
// is "no rows found" — the Go equivalent of catching a ModelNotFoundException
// in Laravel or ObjectDoesNotExist in Django.
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
//
// Returns 204 No Content on success (no response body).
// This is the REST convention for successful deletions.
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
