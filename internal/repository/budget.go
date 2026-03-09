// Package repository — budget.go provides database operations for budgets.
//
// Think of this like a Laravel Eloquent model's query methods. It handles
// basic CRUD plus the join with spending data for the current month.
package repository

import (
	"context"
	"database/sql"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// BudgetRepo handles database operations for budgets.
type BudgetRepo struct {
	db *sql.DB
}

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
// This is the main query used by the dashboard and budget management page.
func (r *BudgetRepo) GetAllWithSpending(ctx context.Context, year int, month time.Month) ([]models.BudgetWithSpending, error) {
	startDate := time.Date(year, month, 1, 0, 0, 0, 0, time.UTC)
	endDate := startDate.AddDate(0, 1, 0)

	rows, err := r.db.QueryContext(ctx, `
		SELECT b.id, b.category_id, b.monthly_limit, b.currency, b.is_active,
		       b.created_at, b.updated_at,
		       c.name AS category_name,
		       COALESCE(SUM(t.amount), 0) AS spent
		FROM budgets b
		JOIN categories c ON b.category_id = c.id
		LEFT JOIN transactions t ON t.category_id = b.category_id
		    AND t.type = 'expense'
		    AND t.date >= $1 AND t.date < $2
		    AND t.currency = b.currency
		WHERE b.is_active = true
		GROUP BY b.id, c.name
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
			&bws.CategoryName, &bws.Spent); err != nil {
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
