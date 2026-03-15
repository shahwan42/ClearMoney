// category.go — CategoryService manages expense/income categories.
//
// Categories are predefined labels for transactions (e.g., "Groceries", "Salary").
// Some are "system" categories (seeded at setup, cannot be modified/deleted),
// others are user-created.
//
// Laravel analogy: Like a CategoryService with system/seeded records protected
// from modification. Similar to how Laravel seeders create default records and
// the service layer guards against their deletion.
//
// Django analogy: Like a Category model with is_system flag and a service layer
// that prevents modification of system records (similar to Django's built-in
// permissions but simpler).
package service

import (
	"context"
	"fmt"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
)

// CategoryService handles business logic for categories.
// Follows the same struct + constructor pattern as all services in this package.
type CategoryService struct {
	repo *repository.CategoryRepo
}

func NewCategoryService(repo *repository.CategoryRepo) *CategoryService {
	return &CategoryService{repo: repo}
}

// GetAll returns all categories (both expense and income).
func (s *CategoryService) GetAll(ctx context.Context) ([]models.Category, error) {
	return s.repo.GetAll(ctx)
}

// GetByType returns categories filtered by type ("expense" or "income").
// models.CategoryType is a string alias — Go uses type aliases for domain semantics.
// Like Laravel's enum cast or Django's TextChoices.
func (s *CategoryService) GetByType(ctx context.Context, catType models.CategoryType) ([]models.Category, error) {
	return s.repo.GetByType(ctx, catType)
}

// GetByID returns a single category by its UUID.
func (s *CategoryService) GetByID(ctx context.Context, id string) (models.Category, error) {
	return s.repo.GetByID(ctx, id)
}

// Create validates and creates a new user-defined category.
func (s *CategoryService) Create(ctx context.Context, cat models.Category) (models.Category, error) {
	var err error
	if cat.Name, err = requireTrimmedName(cat.Name, "category name"); err != nil {
		return models.Category{}, err
	}
	if cat.Type != models.CategoryTypeExpense && cat.Type != models.CategoryTypeIncome {
		return models.Category{}, fmt.Errorf("category type must be 'expense' or 'income'")
	}
	return s.repo.Create(ctx, cat)
}

// Update modifies a category. System categories cannot be renamed.
//
// Pattern: "fetch then check" — we load the existing record to verify it's
// not a system category before allowing modification. In Laravel, you'd do
// the same in a policy or FormRequest. In Go, this guard logic lives here
// in the service layer.
func (s *CategoryService) Update(ctx context.Context, cat models.Category) (models.Category, error) {
	// Load the existing record to check the IsSystem flag.
	// This is an extra DB query, but it ensures system categories can't be modified.
	existing, err := s.repo.GetByID(ctx, cat.ID)
	if err != nil {
		return models.Category{}, err
	}
	if existing.IsSystem {
		return models.Category{}, fmt.Errorf("system categories cannot be modified")
	}
	if cat.Name, err = requireTrimmedName(cat.Name, "category name"); err != nil {
		return models.Category{}, err
	}
	return s.repo.Update(ctx, cat)
}

// Archive soft-deletes a category. System categories cannot be archived.
// Like Laravel's SoftDeletes trait — the record stays in the DB with a
// deleted_at/archived timestamp, but is excluded from normal queries.
func (s *CategoryService) Archive(ctx context.Context, id string) error {
	existing, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return err
	}
	if existing.IsSystem {
		return fmt.Errorf("system categories cannot be archived")
	}
	return s.repo.Archive(ctx, id)
}
