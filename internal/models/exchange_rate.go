// Package models — exchange_rate.go defines the ExchangeRateLog model.
//
// This is an append-only log table — records are inserted but never updated or
// deleted. Each row captures the USD/EGP exchange rate on a given day.
//
// Laravel analogy: Like a Log model that only uses Model::create() — no update()
// or delete() methods. Notice there's no UpdatedAt field, which is intentional.
// In Laravel, you'd set public $timestamps = false or only define CREATED_AT.
//
// Django analogy: Like a Model with auto_now_add=True on created_at but no
// auto_now field. You might also enforce immutability by overriding save() to
// prevent updates.
//
// This table is used for:
//   - Converting USD account balances to EGP for net worth calculations
//   - Historical exchange rate lookups for daily snapshots
//   - Displaying rate trends over time
package models

import "time"

// ExchangeRateLog records daily USD/EGP exchange rates for historical tracking.
//
// Design: This is an immutable (append-only) log. Each row is a point-in-time
// snapshot. No UpdatedAt field exists because rows should never be modified
// after insertion — if a correction is needed, insert a new row for that date.
//
// The Rate field stores EGP per 1 USD. For example:
//   - Rate = 50.5 means 1 USD = 50.5 EGP
//   - To convert USD to EGP: usdAmount * rate
//   - To convert EGP to USD: egpAmount / rate
type ExchangeRateLog struct {
	ID        string    `json:"id" db:"id"`
	Date      time.Time `json:"date" db:"date"`               // the date this rate was recorded (one rate per day)
	Rate      float64   `json:"rate" db:"rate"`                // EGP per 1 USD (e.g., 50.5 means 1 USD = 50.5 EGP)
	Source    *string   `json:"source,omitempty" db:"source"`  // *string = nullable; where the rate came from (e.g., "CBE", "manual"). Nullable because early entries may not have a source.
	Note      *string   `json:"note,omitempty" db:"note"`      // optional context for the entry
	CreatedAt time.Time `json:"created_at" db:"created_at"`    // no UpdatedAt — log entries are immutable (append-only)
}
