// Package repository — exchange_rate.go handles the exchange_rate_log table.
//
// This repository tracks historical USD/EGP exchange rates for multi-currency
// net worth calculations. Rates are logged manually by the user.
//
// Note: Exchange rates are GLOBAL data — they are the same for all users.
// This table does NOT have a user_id column.
//
// Note: ExchangeRateLog is defined here (not in models/) because it's only used
// by the repository layer. If other packages needed it, it would move to models/.
// This is a pragmatic Go pattern — keep types close to where they're used.
//
//   Laravel analogy:  ExchangeRateLog Eloquent model for a simple append-only log table
//   Django analogy:   ExchangeRateLog model with objects.create() and objects.latest()
package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"
)

// ExchangeRateLog records a historical exchange rate entry.
//
// This struct is defined in the repository package (not models/) because
// it's only used here and in the service layer. The json tags enable
// JSON serialization if needed (e.g., for API responses).
//
// *string fields (Source, Note) are pointers because the DB columns are nullable.
// The json:"source,omitempty" tag means: omit from JSON output if nil.
type ExchangeRateLog struct {
	ID        string    `json:"id"`
	Date      time.Time `json:"date"`
	Rate      float64   `json:"rate"`
	Source    *string   `json:"source,omitempty"`
	Note      *string   `json:"note,omitempty"`
	CreatedAt time.Time `json:"created_at"`
}

// ExchangeRateRepo handles database operations for the exchange_rate_log table.
type ExchangeRateRepo struct {
	db *sql.DB
}

// NewExchangeRateRepo creates a new ExchangeRateRepo with the given database connection pool.
func NewExchangeRateRepo(db *sql.DB) *ExchangeRateRepo {
	return &ExchangeRateRepo{db: db}
}

// Log inserts an exchange rate record into the append-only log table.
// This is an INSERT-only operation — rates are never updated or deleted.
// Uses ExecContext (not QueryRowContext) because we don't need any data back.
//
//	Laravel:  ExchangeRateLog::create(['date' => $date, 'rate' => $rate, ...])
//	Django:   ExchangeRateLog.objects.create(date=date, rate=rate, ...)
func (r *ExchangeRateRepo) Log(ctx context.Context, date time.Time, rate float64, source, note *string) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO exchange_rate_log (date, rate, source, note) VALUES ($1, $2, $3, $4)
	`, date, rate, source, note)
	if err != nil {
		return fmt.Errorf("logging exchange rate: %w", err)
	}
	return nil
}

// GetAll retrieves all exchange rate records, newest first.
func (r *ExchangeRateRepo) GetAll(ctx context.Context) ([]ExchangeRateLog, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, date, rate, source, note, created_at
		FROM exchange_rate_log ORDER BY date DESC, created_at DESC
	`)
	if err != nil {
		return nil, fmt.Errorf("querying exchange rates: %w", err)
	}
	defer rows.Close()

	var rates []ExchangeRateLog
	for rows.Next() {
		var rate ExchangeRateLog
		if err := rows.Scan(&rate.ID, &rate.Date, &rate.Rate, &rate.Source, &rate.Note, &rate.CreatedAt); err != nil {
			return nil, fmt.Errorf("scanning exchange rate: %w", err)
		}
		rates = append(rates, rate)
	}
	return rates, rows.Err()
}

// GetLatest retrieves the most recent exchange rate value (just the number, not the full record).
// Used by the dashboard and snapshot service for net worth calculations.
//
// ORDER BY date DESC, created_at DESC LIMIT 1 gets the newest entry.
//
//	Laravel:  ExchangeRateLog::latest('date')->value('rate')
//	Django:   ExchangeRateLog.objects.latest('date').rate
func (r *ExchangeRateRepo) GetLatest(ctx context.Context) (float64, error) {
	var rate float64
	err := r.db.QueryRowContext(ctx, `
		SELECT rate FROM exchange_rate_log ORDER BY date DESC, created_at DESC LIMIT 1
	`).Scan(&rate)
	if err != nil {
		return 0, fmt.Errorf("getting latest rate: %w", err)
	}
	return rate, nil
}
