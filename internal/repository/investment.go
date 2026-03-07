// Package repository — InvestmentRepo handles CRUD for investment holdings.
// Like Laravel's Eloquent model for an investments table.
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

type InvestmentRepo struct {
	db *sql.DB
}

func NewInvestmentRepo(db *sql.DB) *InvestmentRepo {
	return &InvestmentRepo{db: db}
}

// Create inserts a new investment holding.
func (r *InvestmentRepo) Create(ctx context.Context, inv models.Investment) (models.Investment, error) {
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO investments (platform, fund_name, units, last_unit_price, currency)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, last_updated, created_at, updated_at
	`, inv.Platform, inv.FundName, inv.Units, inv.LastUnitPrice, inv.Currency,
	).Scan(&inv.ID, &inv.LastUpdated, &inv.CreatedAt, &inv.UpdatedAt)
	if err != nil {
		return inv, fmt.Errorf("creating investment: %w", err)
	}
	return inv, nil
}

// GetAll returns all investments ordered by platform, fund name.
func (r *InvestmentRepo) GetAll(ctx context.Context) ([]models.Investment, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, platform, fund_name, units, last_unit_price, currency,
			last_updated, created_at, updated_at
		FROM investments ORDER BY platform, fund_name
	`)
	if err != nil {
		return nil, fmt.Errorf("querying investments: %w", err)
	}
	defer rows.Close()

	var investments []models.Investment
	for rows.Next() {
		var inv models.Investment
		if err := rows.Scan(&inv.ID, &inv.Platform, &inv.FundName,
			&inv.Units, &inv.LastUnitPrice, &inv.Currency,
			&inv.LastUpdated, &inv.CreatedAt, &inv.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scanning investment: %w", err)
		}
		investments = append(investments, inv)
	}
	return investments, rows.Err()
}

// GetByID retrieves a single investment.
func (r *InvestmentRepo) GetByID(ctx context.Context, id string) (models.Investment, error) {
	var inv models.Investment
	err := r.db.QueryRowContext(ctx, `
		SELECT id, platform, fund_name, units, last_unit_price, currency,
			last_updated, created_at, updated_at
		FROM investments WHERE id = $1
	`, id).Scan(&inv.ID, &inv.Platform, &inv.FundName,
		&inv.Units, &inv.LastUnitPrice, &inv.Currency,
		&inv.LastUpdated, &inv.CreatedAt, &inv.UpdatedAt)
	if err != nil {
		return inv, fmt.Errorf("getting investment: %w", err)
	}
	return inv, nil
}

// UpdateValuation updates the unit price and last_updated timestamp.
func (r *InvestmentRepo) UpdateValuation(ctx context.Context, id string, unitPrice float64) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE investments SET last_unit_price = $2, last_updated = NOW(), updated_at = NOW()
		WHERE id = $1
	`, id, unitPrice)
	return err
}

// Delete removes an investment.
func (r *InvestmentRepo) Delete(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM investments WHERE id = $1`, id)
	return err
}

// GetTotalValuation returns the sum of (units * last_unit_price) for all investments.
func (r *InvestmentRepo) GetTotalValuation(ctx context.Context) (float64, error) {
	var total sql.NullFloat64
	err := r.db.QueryRowContext(ctx, `
		SELECT SUM(units * last_unit_price) FROM investments
	`).Scan(&total)
	if err != nil {
		return 0, err
	}
	if !total.Valid {
		return 0, nil
	}
	return total.Float64, nil
}
