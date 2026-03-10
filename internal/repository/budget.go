// Package repository — budget.go provides database operations for monthly budgets.
//
// Budgets set spending limits per category per month. The key method is
// GetAllWithSpending() which JOINs budgets with actual transaction spending
// to compute how much has been spent vs. the limit.
//
//   Laravel analogy:  Budget Eloquent model with a scope that joins transactions
//                     and uses selectRaw() for SUM/COALESCE aggregations.
//   Django analogy:   Budget.objects.annotate(spent=Sum('transactions__amount'))
//                     with conditional filtering and F() expressions.
//
// The traffic-light status (green/amber/red) is computed in Go after scanning
// the rows — this keeps SQL focused on data retrieval and Go handles presentation logic.
package repository

import (
	"context"
	"database/sql"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// BudgetRepo handles database operations for the budgets table.
//   Laravel:  BudgetRepository or Budget Eloquent model
//   Django:   Budget.objects (Manager)
type BudgetRepo struct {
	db *sql.DB
}

// NewBudgetRepo creates a new BudgetRepo with the given database connection pool.
func NewBudgetRepo(db *sql.DB) *BudgetRepo {
	return &BudgetRepo{db: db}
}

// GetAll returns all active budgets.
func (r *BudgetRepo) GetAll(ctx context.Context) ([]models.Budget, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, category_id, monthly_limit, currency, is_active, created_at, updated_at
		FROM budgets WHERE is_active = true
		ORDER BY created_at
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var budgets []models.Budget
	for rows.Next() {
		var b models.Budget
		if err := rows.Scan(&b.ID, &b.CategoryID, &b.MonthlyLimit, &b.Currency,
			&b.IsActive, &b.CreatedAt, &b.UpdatedAt); err != nil {
			return nil, err
		}
		budgets = append(budgets, b)
	}
	return budgets, rows.Err()
}

// GetAllWithSpending returns budgets joined with current month's actual spending.
// This is the most complex query in the budget repo — it joins 3 tables.
//
// SQL breakdown:
//   - JOIN categories c: gets the category name for display
//   - LEFT JOIN transactions t: sums up expense amounts for the date range
//     LEFT JOIN (not INNER) ensures budgets with zero spending still appear
//   - COALESCE(SUM(t.amount), 0): returns 0 instead of NULL when no transactions match
//   - GROUP BY b.id, c.name: required because we're using SUM() aggregate
//
//   Laravel equivalent:
//     Budget::join('categories', ...)->leftJoin('transactions', ...)
//       ->selectRaw('COALESCE(SUM(t.amount), 0) as spent')
//       ->groupBy('b.id', 'c.name')->get()
//
//   Django equivalent:
//     Budget.objects.filter(is_active=True)
//       .annotate(category_name=F('category__name'),
//                 spent=Coalesce(Sum('category__transaction__amount', filter=Q(...)), 0))
//
// After scanning, Go computes derived fields (remaining, percentage, status).
// This keeps SQL focused on data retrieval and Go handles presentation logic.
func (r *BudgetRepo) GetAllWithSpending(ctx context.Context, year int, month time.Month) ([]models.BudgetWithSpending, error) {
	startDate := time.Date(year, month, 1, 0, 0, 0, 0, time.UTC)
	endDate := startDate.AddDate(0, 1, 0)

	rows, err := r.db.QueryContext(ctx, `
		SELECT b.id, b.category_id, b.monthly_limit, b.currency, b.is_active,
		       b.created_at, b.updated_at,
		       c.name AS category_name,
		       COALESCE(c.icon, '') AS category_icon,
		       COALESCE(SUM(t.amount), 0) AS spent
		FROM budgets b
		JOIN categories c ON b.category_id = c.id
		LEFT JOIN transactions t ON t.category_id = b.category_id
		    AND t.type = 'expense'
		    AND t.date >= $1 AND t.date < $2
		    AND t.currency = b.currency::currency_type
		WHERE b.is_active = true
		GROUP BY b.id, c.name, c.icon
		ORDER BY c.name
	`, startDate, endDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var result []models.BudgetWithSpending
	for rows.Next() {
		var bws models.BudgetWithSpending
		if err := rows.Scan(&bws.ID, &bws.CategoryID, &bws.MonthlyLimit, &bws.Currency,
			&bws.IsActive, &bws.CreatedAt, &bws.UpdatedAt,
			&bws.CategoryName, &bws.CategoryIcon, &bws.Spent); err != nil {
			return nil, err
		}
		// Compute derived fields
		bws.Remaining = bws.MonthlyLimit - bws.Spent
		if bws.MonthlyLimit > 0 {
			bws.Percentage = bws.Spent / bws.MonthlyLimit * 100
		}
		switch {
		case bws.Percentage >= 90:
			bws.Status = "red"
		case bws.Percentage >= 70:
			bws.Status = "amber"
		default:
			bws.Status = "green"
		}
		result = append(result, bws)
	}
	return result, rows.Err()
}

// Create inserts a new budget.
func (r *BudgetRepo) Create(ctx context.Context, b models.Budget) (models.Budget, error) {
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO budgets (category_id, monthly_limit, currency)
		VALUES ($1, $2, $3)
		RETURNING id, category_id, monthly_limit, currency, is_active, created_at, updated_at
	`, b.CategoryID, b.MonthlyLimit, b.Currency).Scan(
		&b.ID, &b.CategoryID, &b.MonthlyLimit, &b.Currency,
		&b.IsActive, &b.CreatedAt, &b.UpdatedAt)
	return b, err
}

// Delete removes a budget by ID.
func (r *BudgetRepo) Delete(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM budgets WHERE id = $1`, id)
	return err
}

// GetByID returns a single budget by ID.
func (r *BudgetRepo) GetByID(ctx context.Context, id string) (models.Budget, error) {
	var b models.Budget
	err := r.db.QueryRowContext(ctx, `
		SELECT id, category_id, monthly_limit, currency, is_active, created_at, updated_at
		FROM budgets WHERE id = $1
	`, id).Scan(&b.ID, &b.CategoryID, &b.MonthlyLimit, &b.Currency,
		&b.IsActive, &b.CreatedAt, &b.UpdatedAt)
	return b, err
}
