// Package repository — InstallmentRepo handles CRUD for installment payment plans.
//
// Installment plans track purchases paid over multiple months (e.g., a phone bought
// for 12,000 EGP in 12 monthly installments of 1,000 EGP). Each time a payment is
// made, remaining_installments is decremented by 1.
//
//   Laravel analogy:  InstallmentPlan Eloquent model with a decrement('remaining_installments')
//   Django analogy:   InstallmentPlan model with F('remaining_installments') - 1
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/shahwan42/clearmoney/internal/models"
)

// InstallmentRepo handles database operations for the installment_plans table.
type InstallmentRepo struct {
	db *sql.DB
}

// NewInstallmentRepo creates a new InstallmentRepo with the given database connection pool.
func NewInstallmentRepo(db *sql.DB) *InstallmentRepo {
	return &InstallmentRepo{db: db}
}

// Create inserts a new installment plan.
func (r *InstallmentRepo) Create(ctx context.Context, plan models.InstallmentPlan) (models.InstallmentPlan, error) {
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO installment_plans (account_id, description, total_amount, num_installments, monthly_amount, start_date, remaining_installments)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, created_at, updated_at
	`, plan.AccountID, plan.Description, plan.TotalAmount,
		plan.NumInstallments, plan.MonthlyAmount, plan.StartDate, plan.RemainingInstallments,
	).Scan(&plan.ID, &plan.CreatedAt, &plan.UpdatedAt)
	if err != nil {
		return plan, fmt.Errorf("creating installment plan: %w", err)
	}
	return plan, nil
}

// GetAll returns all installment plans ordered by remaining installments (active first).
// Plans with more remaining payments appear first so the user sees active plans at the top.
//   Laravel:  InstallmentPlan::orderByDesc('remaining_installments')->orderByDesc('start_date')->get()
//   Django:   InstallmentPlan.objects.order_by('-remaining_installments', '-start_date')
func (r *InstallmentRepo) GetAll(ctx context.Context) ([]models.InstallmentPlan, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, account_id, description, total_amount, num_installments,
			monthly_amount, start_date, remaining_installments, created_at, updated_at
		FROM installment_plans
		ORDER BY remaining_installments DESC, start_date DESC
	`)
	if err != nil {
		return nil, fmt.Errorf("querying installment plans: %w", err)
	}
	defer rows.Close()

	var plans []models.InstallmentPlan
	for rows.Next() {
		var p models.InstallmentPlan
		if err := rows.Scan(&p.ID, &p.AccountID, &p.Description, &p.TotalAmount,
			&p.NumInstallments, &p.MonthlyAmount, &p.StartDate,
			&p.RemainingInstallments, &p.CreatedAt, &p.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scanning installment plan: %w", err)
		}
		plans = append(plans, p)
	}
	return plans, rows.Err()
}

// GetByID retrieves a single installment plan.
func (r *InstallmentRepo) GetByID(ctx context.Context, id string) (models.InstallmentPlan, error) {
	var p models.InstallmentPlan
	err := r.db.QueryRowContext(ctx, `
		SELECT id, account_id, description, total_amount, num_installments,
			monthly_amount, start_date, remaining_installments, created_at, updated_at
		FROM installment_plans WHERE id = $1
	`, id).Scan(&p.ID, &p.AccountID, &p.Description, &p.TotalAmount,
		&p.NumInstallments, &p.MonthlyAmount, &p.StartDate,
		&p.RemainingInstallments, &p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		return p, fmt.Errorf("getting installment plan: %w", err)
	}
	return p, nil
}

// RecordPayment decrements remaining_installments by 1.
//
// The WHERE clause includes `remaining_installments > 0` as a safety guard —
// prevents going negative if called on an already-completed plan.
// The arithmetic happens at the DB level for atomicity.
//
//   Laravel:  InstallmentPlan::where('id', $id)->where('remaining_installments', '>', 0)->decrement('remaining_installments')
//   Django:   InstallmentPlan.objects.filter(id=id, remaining_installments__gt=0).update(remaining_installments=F('remaining_installments') - 1)
func (r *InstallmentRepo) RecordPayment(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE installment_plans
		SET remaining_installments = remaining_installments - 1, updated_at = NOW()
		WHERE id = $1 AND remaining_installments > 0
	`, id)
	return err
}

// Delete removes an installment plan.
func (r *InstallmentRepo) Delete(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM installment_plans WHERE id = $1`, id)
	return err
}
