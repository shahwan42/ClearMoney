// Package repository — InvestmentRepo handles CRUD for investment holdings.
//
// Investments track units held in funds/platforms with a "units * price" valuation
// model. The user updates the unit price manually, and the total valuation is
// computed as SUM(units * last_unit_price) across all holdings.
//
//   Laravel analogy:  Investment Eloquent model with an accessor for computed value
//   Django analogy:   Investment model with a property for valuation, plus annotate()/aggregate()
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// InvestmentRepo handles database operations for the investments table.
type InvestmentRepo struct {
	db *sql.DB
}

// NewInvestmentRepo creates a new InvestmentRepo with the given database connection pool.
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
// NOW() is PostgreSQL's current timestamp function (server-side, not Go-side).
// Using server-side time ensures consistency regardless of client clock skew.
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
//
// sql.NullFloat64 is used because SUM() returns NULL when there are no rows.
// In Go, you can't scan SQL NULL into a plain float64 — it would error.
// sql.NullFloat64 has two fields: Float64 (the value) and Valid (is it non-NULL?).
//
//   Laravel:  Investment::selectRaw('SUM(units * last_unit_price)')->value('sum')
//   Django:   Investment.objects.aggregate(total=Sum(F('units') * F('last_unit_price')))
//
// Alternative: use COALESCE(SUM(...), 0) in SQL to avoid NullFloat64.
// Both approaches work — this file uses NullFloat64 for demonstration.
// See: https://pkg.go.dev/database/sql#NullFloat64
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
