// Package service implements the business logic layer for ClearMoney.
//
// Laravel analogy: This is equivalent to app/Services/ — the classes you create
// to keep Controllers thin. In Laravel, you might have App\Services\InstitutionService
// that your InstitutionController calls. Same idea here.
//
// Django analogy: This is the service layer that Django doesn't officially have,
// but many projects create as a services.py module alongside views.py. It keeps
// business logic out of views and models.
//
// Key Go differences from PHP/Python:
//   - No exceptions: every function returns (result, error) instead of throwing.
//     The caller MUST check the error. This is Go's most important idiom.
//   - No dependency injection container: dependencies are passed explicitly via
//     constructor functions (NewXxxService) — no Laravel IoC, no Django middleware magic.
//   - context.Context: passed as the first parameter to every method. It carries
//     request-scoped data, deadlines, and cancellation signals. Think of it like
//     Laravel's Request object but only for cancellation/timeout, not HTTP data.
//
// See: https://pkg.go.dev/context for context.Context documentation
// See: https://go.dev/blog/error-handling-and-go for Go error handling patterns
package service

import (
	"context"
	"fmt"
	"strings"

	"github.com/ahmedelsamadisi/clearmoney/internal/logutil"
	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// InstitutionService handles business logic for institutions.
// Like a Laravel Service class — sits between the controller (handler) and
// the Eloquent model (repository). The struct holds its dependencies as fields,
// similar to how Laravel uses constructor injection in service classes.
type InstitutionService struct {
	// repo is the data access layer — like Eloquent or Django ORM calls.
	// In Go, we store it as a pointer field (dependency injection via struct).
	repo *repository.InstitutionRepo
}

// NewInstitutionService creates a service with its repository dependency.
// This is Go's version of constructor injection. In Laravel, you'd type-hint
// InstitutionRepo in the constructor and the IoC container resolves it.
// In Go, we pass it explicitly — no magic, no container.
func NewInstitutionService(repo *repository.InstitutionRepo) *InstitutionService {
	return &InstitutionService{repo: repo}
}

// Create validates and creates a new institution.
// (s *InstitutionService) is a "method receiver" — Go's version of $this in PHP.
// ctx (context.Context) is passed through every layer; it carries request-scoped
// data and cancellation signals (like Laravel's Request object but for timeouts/cancellation).
//
// Returns (models.Institution, error) — Go uses multiple return values instead of
// throwing exceptions. The caller MUST check `err` (like Laravel's try/catch but explicit).
func (s *InstitutionService) Create(ctx context.Context, inst models.Institution) (models.Institution, error) {
	// Validation happens here in the service layer, not in the model.
	// In Laravel you'd use FormRequest or Validator; in Go, we validate manually.
	inst.Name = strings.TrimSpace(inst.Name)
	if inst.Name == "" {
		// fmt.Errorf creates a new error — like throwing new ValidationException in Laravel.
		// The caller receives this as the second return value.
		return models.Institution{}, fmt.Errorf("institution name is required")
	}
	// Default value assignment — like $fillable defaults in Laravel models.
	if inst.Type == "" {
		inst.Type = models.InstitutionTypeBank
	}
	if inst.Type != models.InstitutionTypeBank && inst.Type != models.InstitutionTypeFintech && inst.Type != models.InstitutionTypeWallet {
		return models.Institution{}, fmt.Errorf("invalid institution type: %s", inst.Type)
	}
	// Delegate to the repository for the actual DB insert.
	// The repo returns the created model with its generated ID (like Eloquent's create()).
	created, err := s.repo.Create(ctx, inst)
	if err != nil {
		return models.Institution{}, err
	}
	logutil.LogEvent(ctx, "institution.created", "type", string(created.Type))
	return created, nil
}

// GetByID retrieves an institution by ID.
// Like Eloquent's Institution::findOrFail($id) or Django's Institution.objects.get(id=id).
// Returns an error if not found (no exceptions — Go uses error return values).
func (s *InstitutionService) GetByID(ctx context.Context, id string) (models.Institution, error) {
	return s.repo.GetByID(ctx, id)
}

// GetAll retrieves all institutions.
// Like Eloquent's Institution::all() or Django's Institution.objects.all().
// Returns an empty slice (not nil) if no records exist.
func (s *InstitutionService) GetAll(ctx context.Context) ([]models.Institution, error) {
	return s.repo.GetAll(ctx)
}

// Update validates and updates an institution.
// The service layer re-validates even on update — unlike Laravel's sometimes() rule,
// Go services typically validate every time since there's no FormRequest magic.
func (s *InstitutionService) Update(ctx context.Context, inst models.Institution) (models.Institution, error) {
	inst.Name = strings.TrimSpace(inst.Name)
	if inst.Name == "" {
		return models.Institution{}, fmt.Errorf("institution name is required")
	}
	updated, err := s.repo.Update(ctx, inst)
	if err != nil {
		return models.Institution{}, err
	}
	logutil.LogEvent(ctx, "institution.updated", "id", inst.ID)
	return updated, nil
}

// Delete removes an institution by ID.
// Note: returns only error, not (model, error). When a Go function returns
// a single error, it means the operation either succeeded (nil) or failed (non-nil).
// This is like Laravel's $institution->delete() which returns bool.
func (s *InstitutionService) Delete(ctx context.Context, id string) error {
	if err := s.repo.Delete(ctx, id); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "institution.deleted", "id", id)
	return nil
}

// UpdateDisplayOrder sets the display order for an institution.
// Used for drag-and-drop reordering in the UI. The order int maps to
// a display_order column in the database (like Laravel's sortable trait).
func (s *InstitutionService) UpdateDisplayOrder(ctx context.Context, id string, order int) error {
	return s.repo.UpdateDisplayOrder(ctx, id, order)
}
