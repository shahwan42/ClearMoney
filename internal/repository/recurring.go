// Package repository — RecurringRepo handles CRUD for recurring transaction rules.
// Like Laravel's Eloquent model for a recurring_rules table.
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// RecurringRepo handles database operations for recurring rules.
type RecurringRepo struct {
	db *sql.DB
}

func NewRecurringRepo(db *sql.DB) *RecurringRepo {
	return &RecurringRepo{db: db}
}

// Create inserts a new recurring rule.
func (r *RecurringRepo) Create(ctx context.Context, rule models.RecurringRule) (models.RecurringRule, error) {
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO recurring_rules (template_transaction, frequency, day_of_month, next_due_date, is_active, auto_confirm)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, created_at, updated_at
	`, rule.TemplateTransaction, rule.Frequency, rule.DayOfMonth,
		rule.NextDueDate, rule.IsActive, rule.AutoConfirm,
	).Scan(&rule.ID, &rule.CreatedAt, &rule.UpdatedAt)
	if err != nil {
		return rule, fmt.Errorf("creating recurring rule: %w", err)
	}
	return rule, nil
}

// GetByID retrieves a recurring rule by ID.
func (r *RecurringRepo) GetByID(ctx context.Context, id string) (models.RecurringRule, error) {
	var rule models.RecurringRule
	err := r.db.QueryRowContext(ctx, `
		SELECT id, template_transaction, frequency, day_of_month, next_due_date,
			is_active, auto_confirm, created_at, updated_at
		FROM recurring_rules WHERE id = $1
	`, id).Scan(&rule.ID, &rule.TemplateTransaction, &rule.Frequency,
		&rule.DayOfMonth, &rule.NextDueDate,
		&rule.IsActive, &rule.AutoConfirm, &rule.CreatedAt, &rule.UpdatedAt)
	if err != nil {
		return rule, fmt.Errorf("getting recurring rule: %w", err)
	}
	return rule, nil
}

// GetAll retrieves all recurring rules.
func (r *RecurringRepo) GetAll(ctx context.Context) ([]models.RecurringRule, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, template_transaction, frequency, day_of_month, next_due_date,
			is_active, auto_confirm, created_at, updated_at
		FROM recurring_rules ORDER BY next_due_date ASC
	`)
	if err != nil {
		return nil, fmt.Errorf("querying recurring rules: %w", err)
	}
	defer rows.Close()

	var rules []models.RecurringRule
	for rows.Next() {
		var rule models.RecurringRule
		if err := rows.Scan(&rule.ID, &rule.TemplateTransaction, &rule.Frequency,
			&rule.DayOfMonth, &rule.NextDueDate,
			&rule.IsActive, &rule.AutoConfirm, &rule.CreatedAt, &rule.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scanning recurring rule: %w", err)
		}
		rules = append(rules, rule)
	}
	return rules, rows.Err()
}

// GetDue retrieves all active rules where next_due_date <= today.
func (r *RecurringRepo) GetDue(ctx context.Context) ([]models.RecurringRule, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, template_transaction, frequency, day_of_month, next_due_date,
			is_active, auto_confirm, created_at, updated_at
		FROM recurring_rules
		WHERE is_active = true AND next_due_date <= CURRENT_DATE
		ORDER BY next_due_date ASC
	`)
	if err != nil {
		return nil, fmt.Errorf("querying due rules: %w", err)
	}
	defer rows.Close()

	var rules []models.RecurringRule
	for rows.Next() {
		var rule models.RecurringRule
		if err := rows.Scan(&rule.ID, &rule.TemplateTransaction, &rule.Frequency,
			&rule.DayOfMonth, &rule.NextDueDate,
			&rule.IsActive, &rule.AutoConfirm, &rule.CreatedAt, &rule.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scanning due rule: %w", err)
		}
		rules = append(rules, rule)
	}
	return rules, rows.Err()
}

// UpdateNextDueDate advances the next_due_date for a rule.
func (r *RecurringRepo) UpdateNextDueDate(ctx context.Context, id string, nextDate interface{}) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE recurring_rules SET next_due_date = $2, updated_at = NOW() WHERE id = $1
	`, id, nextDate)
	return err
}

// Delete removes a recurring rule.
func (r *RecurringRepo) Delete(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM recurring_rules WHERE id = $1`, id)
	return err
}
