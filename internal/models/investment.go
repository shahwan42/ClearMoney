package models

import "time"

// Investment represents a fund holding on a platform like Thndr.
// Valuation = Units * LastUnitPrice (computed via method, not stored in DB).
//
// Go pattern: Valuation() is a method on the struct (like an accessor/getter in Laravel
// or a @property in Django) — but it must be called explicitly, not auto-computed.
type Investment struct {
	ID            string    `json:"id" db:"id"`
	Platform      string    `json:"platform" db:"platform"`       // e.g., "Thndr", "EFG Hermes"
	FundName      string    `json:"fund_name" db:"fund_name"`     // e.g., "Banque Misr Money Market Fund"
	Units         float64   `json:"units" db:"units"`             // number of fund units owned
	LastUnitPrice float64   `json:"last_unit_price" db:"last_unit_price"` // latest NAV per unit
	Currency      Currency  `json:"currency" db:"currency"`
	LastUpdated   time.Time `json:"last_updated" db:"last_updated"` // when the unit price was last refreshed
	CreatedAt     time.Time `json:"created_at" db:"created_at"`
	UpdatedAt     time.Time `json:"updated_at" db:"updated_at"`
}

// Valuation returns units * last_unit_price.
func (i Investment) Valuation() float64 {
	return i.Units * i.LastUnitPrice
}
