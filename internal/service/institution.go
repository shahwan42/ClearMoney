// Package service implements the business logic layer.
//
// This sits between handlers and repositories — like Laravel's Service classes
// or Django's business logic in views/services. Services validate input,
// enforce business rules, and coordinate between repositories.
//
// Services don't know about HTTP (no request/response). They accept
// plain Go types and return models or errors.
package service

import (
	"context"
	"fmt"
	"strings"

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
	if inst.Type != models.InstitutionTypeBank && inst.Type != models.InstitutionTypeFintech {
		return models.Institution{}, fmt.Errorf("invalid institution type: %s", inst.Type)
	}
	// Delegate to the repository for the actual DB insert.
	// The repo returns the created model with its generated ID (like Eloquent's create()).
	return s.repo.Create(ctx, inst)
}

// GetByID retrieves an institution by ID.
func (s *InstitutionService) GetByID(ctx context.Context, id string) (models.Institution, error) {
	return s.repo.GetByID(ctx, id)
}

// GetAll retrieves all institutions.
func (s *InstitutionService) GetAll(ctx context.Context) ([]models.Institution, error) {
	return s.repo.GetAll(ctx)
}

// Update validates and updates an institution.
func (s *InstitutionService) Update(ctx context.Context, inst models.Institution) (models.Institution, error) {
	inst.Name = strings.TrimSpace(inst.Name)
	if inst.Name == "" {
		return models.Institution{}, fmt.Errorf("institution name is required")
	}
	return s.repo.Update(ctx, inst)
}

// Delete removes an institution by ID.
func (s *InstitutionService) Delete(ctx context.Context, id string) error {
	return s.repo.Delete(ctx, id)
}

// UpdateDisplayOrder sets the display order for an institution.
func (s *InstitutionService) UpdateDisplayOrder(ctx context.Context, id string, order int) error {
	return s.repo.UpdateDisplayOrder(ctx, id, order)
}
