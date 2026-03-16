// Package models — investment.go defines the Investment model for fund holdings.
//
// Investments track fund holdings on platforms like Thndr or EFG Hermes.
// Unlike bank accounts (which track exact balances), investment values are
// computed from units * unit_price, and the price changes over time as the
// fund's NAV (Net Asset Value) updates.
//
// Laravel analogy: An Eloquent model with a computed accessor for valuation.
// In Laravel, you'd define getValuationAttribute() which returns units * price.
// The key difference in Go is that computed values are regular methods, not
// magic getters — you call i.Valuation() explicitly (not i.valuation).
//
// Django analogy: A Model with a @property for valuation. Same concept,
// different syntax.
package models

import "time"

// Investment represents a fund holding on a platform like Thndr.
//
// Valuation is NOT stored in the database — it's computed on demand via the
// Valuation() method. This avoids stale data: since LastUnitPrice changes
// frequently, storing a pre-computed valuation would require constant updates.
//
// The LastUpdated timestamp tracks when the unit price was last refreshed
// (which is different from UpdatedAt, which tracks when any field was modified).
type Investment struct {
	ID            string    `json:"id" db:"id"`
	UserID        string    `json:"user_id" db:"user_id"`
	Platform      string    `json:"platform" db:"platform"`              // investment platform name (e.g., "Thndr", "EFG Hermes")
	FundName      string    `json:"fund_name" db:"fund_name"`            // specific fund name (e.g., "Banque Misr Money Market Fund")
	Units         float64   `json:"units" db:"units"`                    // number of fund units owned (can be fractional, e.g., 152.347)
	LastUnitPrice float64   `json:"last_unit_price" db:"last_unit_price"` // latest NAV (Net Asset Value) per unit — updated periodically
	Currency      Currency  `json:"currency" db:"currency"`              // which currency the fund is denominated in
	LastUpdated   time.Time `json:"last_updated" db:"last_updated"`      // when LastUnitPrice was last refreshed (separate from UpdatedAt)
	CreatedAt     time.Time `json:"created_at" db:"created_at"`
	UpdatedAt     time.Time `json:"updated_at" db:"updated_at"`
}

// Valuation returns the current market value of this holding: units * last_unit_price.
//
// This is a COMPUTED PROPERTY implemented as a value-receiver method.
//
// Important Go distinction from PHP/Python:
//   - In PHP/Laravel:  $investment->valuation is auto-called via __get() magic
//   - In Python/Django: investment.valuation uses @property decorator
//   - In Go:            investment.Valuation() must be called explicitly with ()
//
// Go has no "magic methods" or property decorators. In regular Go code, methods
// are always called with parentheses: investment.Valuation().
// However, Go templates DO call zero-argument methods automatically without () —
// so {{ .Valuation }} works in templates because the template engine recognizes
// it as a method and invokes it. This makes templates feel closer to Laravel/Django
// where you'd write {{ $investment->valuation }} or {{ investment.valuation }}.
func (i Investment) Valuation() float64 {
	return i.Units * i.LastUnitPrice
}
