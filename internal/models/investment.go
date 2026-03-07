package models

import "time"

// Investment represents a fund holding on a platform like Thndr.
// Similar to a Laravel Investment model or Django's Investment model.
// Valuation = Units * LastUnitPrice (computed, not stored).
type Investment struct {
	ID            string   `json:"id" db:"id"`
	Platform      string   `json:"platform" db:"platform"`
	FundName      string   `json:"fund_name" db:"fund_name"`
	Units         float64  `json:"units" db:"units"`
	LastUnitPrice float64  `json:"last_unit_price" db:"last_unit_price"`
	Currency      Currency `json:"currency" db:"currency"`
	LastUpdated   time.Time `json:"last_updated" db:"last_updated"`
	CreatedAt     time.Time `json:"created_at" db:"created_at"`
	UpdatedAt     time.Time `json:"updated_at" db:"updated_at"`
}

// Valuation returns units * last_unit_price.
func (i Investment) Valuation() float64 {
	return i.Units * i.LastUnitPrice
}
