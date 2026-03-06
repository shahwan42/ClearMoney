package service

import (
	"context"
	"fmt"
	"strings"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// CategoryService handles business logic for categories.
type CategoryService struct {
	repo *repository.CategoryRepo
}

func NewCategoryService(repo *repository.CategoryRepo) *CategoryService {
	return &CategoryService{repo: repo}
}

func (s *CategoryService) GetAll(ctx context.Context) ([]models.Category, error) {
	return s.repo.GetAll(ctx)
}

func (s *CategoryService) GetByType(ctx context.Context, catType models.CategoryType) ([]models.Category, error) {
	return s.repo.GetByType(ctx, catType)
}

func (s *CategoryService) GetByID(ctx context.Context, id string) (models.Category, error) {
	return s.repo.GetByID(ctx, id)
}

func (s *CategoryService) Create(ctx context.Context, cat models.Category) (models.Category, error) {
	cat.Name = strings.TrimSpace(cat.Name)
	if cat.Name == "" {
		return models.Category{}, fmt.Errorf("category name is required")
	}
	if cat.Type != models.CategoryTypeExpense && cat.Type != models.CategoryTypeIncome {
		return models.Category{}, fmt.Errorf("category type must be 'expense' or 'income'")
	}
	return s.repo.Create(ctx, cat)
}

// Update modifies a category. System categories cannot be renamed.
func (s *CategoryService) Update(ctx context.Context, cat models.Category) (models.Category, error) {
	existing, err := s.repo.GetByID(ctx, cat.ID)
	if err != nil {
		return models.Category{}, err
	}
	if existing.IsSystem {
		return models.Category{}, fmt.Errorf("system categories cannot be modified")
	}
	cat.Name = strings.TrimSpace(cat.Name)
	if cat.Name == "" {
		return models.Category{}, fmt.Errorf("category name is required")
	}
	return s.repo.Update(ctx, cat)
}

// Archive soft-deletes a category. System categories cannot be archived.
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
