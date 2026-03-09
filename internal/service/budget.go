// Package service — budget.go provides business logic for budget management.
//
// Budgets set monthly spending limits per category. The service layer computes
// actual spending by joining budgets with transactions for the current month.
//
// In Laravel terms: BudgetService is like a Service class that wraps the
// Eloquent model. In Django: similar to a Manager or custom QuerySet method.
package service

import (
	"context"
	"fmt"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// BudgetService handles business logic for budgets.
type BudgetService struct {
	budgetRepo *repository.BudgetRepo
}

func NewBudgetService(budgetRepo *repository.BudgetRepo) *BudgetService {
	return &BudgetService{budgetRepo: budgetRepo}
}

// GetAllWithSpending returns budgets with current month's actual spending computed.
func (s *BudgetService) GetAllWithSpending(ctx context.Context) ([]models.BudgetWithSpending, error) {
	now := time.Now()
	return s.budgetRepo.GetAllWithSpending(ctx, now.Year(), now.Month())
}

// GetAll returns all active budgets (without spending data).
func (s *BudgetService) GetAll(ctx context.Context) ([]models.Budget, error) {
	return s.budgetRepo.GetAll(ctx)
}

// Create creates a new budget with validation.
func (s *BudgetService) Create(ctx context.Context, b models.Budget) (models.Budget, error) {
	if b.CategoryID == "" {
		return b, fmt.Errorf("category is required")
	}
	if b.MonthlyLimit <= 0 {
		return b, fmt.Errorf("monthly limit must be positive")
	}
	if b.Currency == "" {
		b.Currency = models.CurrencyEGP
	}
	return s.budgetRepo.Create(ctx, b)
}

// Delete removes a budget by ID.
func (s *BudgetService) Delete(ctx context.Context, id string) error {
	return s.budgetRepo.Delete(ctx, id)
}
