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
type InstitutionService struct {
	repo *repository.InstitutionRepo
}

// NewInstitutionService creates a service with its repository dependency.
func NewInstitutionService(repo *repository.InstitutionRepo) *InstitutionService {
	return &InstitutionService{repo: repo}
}

// Create validates and creates a new institution.
func (s *InstitutionService) Create(ctx context.Context, inst models.Institution) (models.Institution, error) {
	inst.Name = strings.TrimSpace(inst.Name)
	if inst.Name == "" {
		return models.Institution{}, fmt.Errorf("institution name is required")
	}
	if inst.Type == "" {
		inst.Type = models.InstitutionTypeBank
	}
	if inst.Type != models.InstitutionTypeBank && inst.Type != models.InstitutionTypeFintech {
		return models.Institution{}, fmt.Errorf("invalid institution type: %s", inst.Type)
	}
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
