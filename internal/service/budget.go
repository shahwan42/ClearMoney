// Package service — budget.go provides business logic for budget management.
//
// Budgets set monthly spending limits per category. The service layer computes
// actual spending by joining budgets with transactions for the current month.
// The result is a BudgetWithSpending struct that includes the limit, actual spent,
// remaining amount, percentage used, and a status color (green/amber/red).
//
// Laravel analogy: BudgetService is like a Service class that wraps the Budget
// Eloquent model and adds computed spending data. Similar to using withSum() or
// a Resource with appended attributes. In ClearMoney, the computation happens in
// PostgreSQL via a JOIN query in the repository.
//
// Django analogy: Like a Manager method that uses annotate() and F() expressions
// to add computed spending data to the Budget queryset. Or a service function that
// calls Budget.objects.get_with_spending().
//
// The budget's percentage drives UI indicators:
//   - Green: < 80% used (on track)
//   - Amber: 80-99% used (approaching limit)
//   - Red: >= 100% used (over budget)
//
// These thresholds also trigger push notifications (via NotificationService).
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
// The spending data comes from a PostgreSQL JOIN: budgets LEFT JOIN transactions
// grouped by category for the current month. The repo handles the SQL complexity.
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
