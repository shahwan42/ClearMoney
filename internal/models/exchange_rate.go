package models

import "time"

// ExchangeRateLog records daily USD/EGP exchange rates for historical tracking.
// Each row is a snapshot — like a log table you'd create in Laravel with no update/delete.
// Used to convert USD holdings to EGP for net worth calculations.
type ExchangeRateLog struct {
	ID        string    `json:"id" db:"id"`
	Date      time.Time `json:"date" db:"date"`            // the date this rate was recorded
	Rate      float64   `json:"rate" db:"rate"`            // EGP per 1 USD (e.g., 50.5 means 1 USD = 50.5 EGP)
	Source    *string   `json:"source,omitempty" db:"source"` // *string = nullable; where the rate came from (e.g., "CBE", "manual")
	Note      *string   `json:"note,omitempty" db:"note"`
	CreatedAt time.Time `json:"created_at" db:"created_at"` // no UpdatedAt — log entries are immutable (append-only)
}
