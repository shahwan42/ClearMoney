// Package repository — RecurringRepo handles CRUD for recurring transaction rules.
//
// Recurring rules define transactions that repeat on a schedule (monthly rent,
// salary, subscriptions). Each rule has a template_transaction (JSONB) that stores
// the transaction data to replicate, and a next_due_date that advances after
// each execution.
//
//   Laravel analogy:  Scheduled tasks + a recurring_rules table. Like Task Scheduling
//                     but for financial transactions instead of artisan commands.
//   Django analogy:   A model with JSONB template + celery-beat for scheduling.
//
// The template_transaction column uses PostgreSQL JSONB to store a serialized
// transaction template. This avoids needing a separate table for template fields.
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/shahwan42/clearmoney/internal/models"
)

// RecurringRepo handles database operations for the recurring_rules table.
//   Laravel:  RecurringRule model + RecurringRuleRepository
//   Django:   RecurringRule.objects (Manager)
type RecurringRepo struct {
	db *sql.DB
}

// NewRecurringRepo creates a new RecurringRepo with the given database connection pool.
func NewRecurringRepo(db *sql.DB) *RecurringRepo {
	return &RecurringRepo{db: db}
}

// Create inserts a new recurring rule.
// The template_transaction field is JSONB — it stores the transaction blueprint
// as raw JSON bytes (Go type: json.RawMessage in the model).
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
// Called at application startup to process any rules that came due since last run.
//
// CURRENT_DATE is a PostgreSQL built-in that returns today's date (server time).
//   Laravel:  RecurringRule::where('is_active', true)->where('next_due_date', '<=', now())->get()
//   Django:   RecurringRule.objects.filter(is_active=True, next_due_date__lte=date.today())
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

// UpdateNextDueDate advances the next_due_date for a rule after it fires.
// The nextDate parameter uses interface{} (Go's "any" type) to accept both
// time.Time and nil (for disabling a rule by clearing its due date).
//   Laravel:  $rule->update(['next_due_date' => $nextDate])
//   Django:   rule.next_due_date = next_date; rule.save()
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

// DeleteByAccountID removes all recurring rules whose template_transaction references
// the given account_id. Called when an account is deleted to avoid FK violations
// when a stale rule later tries to fire.
//
// The ->> operator extracts a JSONB field as text for string comparison:
//   template_transaction->>'account_id'  reads the "account_id" key from the JSONB blob.
//   Laravel: whereRaw("template_transaction->>'account_id' = ?", [$accountId])->delete()
//   Django:  RecurringRule.objects.filter(template_transaction__account_id=account_id).delete()
func (r *RecurringRepo) DeleteByAccountID(ctx context.Context, accountID string) error {
	_, err := r.db.ExecContext(ctx, `
		DELETE FROM recurring_rules
		WHERE template_transaction->>'account_id' = $1
	`, accountID)
	if err != nil {
		return fmt.Errorf("deleting recurring rules for account: %w", err)
	}
	return nil
}
