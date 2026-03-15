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
	"time"

	"github.com/shahwan42/clearmoney/internal/logutil"
	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/timeutil"
)

// BudgetService handles business logic for budgets.
type BudgetService struct {
	budgetRepo *repository.BudgetRepo
	loc        *time.Location // User timezone for "this month" calculation
}

// SetTimezone sets the user's timezone for calendar-date operations.
func (s *BudgetService) SetTimezone(loc *time.Location) {
	s.loc = loc
}

// timezone returns the configured timezone or UTC as fallback.
func (s *BudgetService) timezone() *time.Location {
	if s.loc != nil {
		return s.loc
	}
	return time.UTC
}

func NewBudgetService(budgetRepo *repository.BudgetRepo) *BudgetService {
	return &BudgetService{budgetRepo: budgetRepo}
}

// GetAllWithSpending returns budgets with current month's actual spending computed.
// The spending data comes from a PostgreSQL JOIN: budgets LEFT JOIN transactions
// grouped by category for the current month. The repo handles the SQL complexity.
func (s *BudgetService) GetAllWithSpending(ctx context.Context) ([]models.BudgetWithSpending, error) {
	now := timeutil.Now().In(s.timezone())
	return s.budgetRepo.GetAllWithSpending(ctx, now.Year(), now.Month())
}

// GetAll returns all active budgets (without spending data).
func (s *BudgetService) GetAll(ctx context.Context) ([]models.Budget, error) {
	return s.budgetRepo.GetAll(ctx)
}

// Create creates a new budget with validation.
func (s *BudgetService) Create(ctx context.Context, b models.Budget) (models.Budget, error) {
	if err := requireNotEmpty(b.CategoryID, "category"); err != nil {
		return b, err
	}
	if err := requirePositive(b.MonthlyLimit, "monthly limit"); err != nil {
		return b, err
	}
	if b.Currency == "" {
		b.Currency = models.CurrencyEGP
	}
	created, err := s.budgetRepo.Create(ctx, b)
	if err != nil {
		return b, err
	}
	logutil.LogEvent(ctx, "budget.created", "currency", string(created.Currency), "category_id", created.CategoryID)
	return created, nil
}

// Delete removes a budget by ID.
func (s *BudgetService) Delete(ctx context.Context, id string) error {
	if err := s.budgetRepo.Delete(ctx, id); err != nil {
		return err
	}
	logutil.LogEvent(ctx, "budget.deleted", "id", id)
	return nil
}
