package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"
)

// ExchangeRateLog records a historical exchange rate.
type ExchangeRateLog struct {
	ID        string    `json:"id"`
	Date      time.Time `json:"date"`
	Rate      float64   `json:"rate"`
	Source    *string   `json:"source,omitempty"`
	Note      *string   `json:"note,omitempty"`
	CreatedAt time.Time `json:"created_at"`
}

// ExchangeRateRepo handles exchange rate log operations.
type ExchangeRateRepo struct {
	db *sql.DB
}

func NewExchangeRateRepo(db *sql.DB) *ExchangeRateRepo {
	return &ExchangeRateRepo{db: db}
}

// Log inserts an exchange rate record.
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

// GetLatest retrieves the most recent exchange rate.
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
