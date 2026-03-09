// Package repository — SnapshotRepo handles CRUD for daily balance snapshots.
// Like a Laravel Eloquent model for daily_snapshots and account_snapshots tables.
//
// Uses PostgreSQL UPSERT (INSERT ... ON CONFLICT DO UPDATE) so snapshots are
// idempotent — running the snapshot job twice for the same day safely updates
// rather than creating duplicates.
package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// SnapshotRepo provides data access for daily_snapshots and account_snapshots.
type SnapshotRepo struct {
	db *sql.DB
}

// NewSnapshotRepo creates a new SnapshotRepo.
func NewSnapshotRepo(db *sql.DB) *SnapshotRepo {
	return &SnapshotRepo{db: db}
}

// UpsertDaily creates or updates a daily snapshot for the given date.
// Uses ON CONFLICT (date) DO UPDATE for idempotency — safe to call multiple times.
//
// In Django: DailySnapshot.objects.update_or_create(date=..., defaults={...})
func (r *SnapshotRepo) UpsertDaily(ctx context.Context, snap models.DailySnapshot) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO daily_snapshots (date, net_worth_egp, net_worth_raw, exchange_rate, daily_spending, daily_income)
		VALUES ($1, $2, $3, $4, $5, $6)
		ON CONFLICT (date) DO UPDATE SET
			net_worth_egp = EXCLUDED.net_worth_egp,
			net_worth_raw = EXCLUDED.net_worth_raw,
			exchange_rate = EXCLUDED.exchange_rate,
			daily_spending = EXCLUDED.daily_spending,
			daily_income = EXCLUDED.daily_income
	`, snap.Date, snap.NetWorthEGP, snap.NetWorthRaw, snap.ExchangeRate,
		snap.DailySpending, snap.DailyIncome)
	if err != nil {
		return fmt.Errorf("upserting daily snapshot: %w", err)
	}
	return nil
}

// UpsertAccount creates or updates an account snapshot for the given date+account.
// Uses ON CONFLICT (date, account_id) DO UPDATE for idempotency.
func (r *SnapshotRepo) UpsertAccount(ctx context.Context, snap models.AccountSnapshot) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO account_snapshots (date, account_id, balance)
		VALUES ($1, $2, $3)
		ON CONFLICT (date, account_id) DO UPDATE SET
			balance = EXCLUDED.balance
	`, snap.Date, snap.AccountID, snap.Balance)
	if err != nil {
		return fmt.Errorf("upserting account snapshot: %w", err)
	}
	return nil
}

// GetDailyRange returns daily snapshots between two dates (inclusive), ordered by date ASC.
// Used for sparklines: e.g., "last 30 days of net worth".
func (r *SnapshotRepo) GetDailyRange(ctx context.Context, from, to time.Time) ([]models.DailySnapshot, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, date, net_worth_egp, net_worth_raw, exchange_rate,
			daily_spending, daily_income, created_at
		FROM daily_snapshots
		WHERE date >= $1 AND date <= $2
		ORDER BY date ASC
	`, from, to)
	if err != nil {
		return nil, fmt.Errorf("querying daily snapshots: %w", err)
	}
	defer rows.Close()

	var snapshots []models.DailySnapshot
	for rows.Next() {
		var s models.DailySnapshot
		if err := rows.Scan(&s.ID, &s.Date, &s.NetWorthEGP, &s.NetWorthRaw,
			&s.ExchangeRate, &s.DailySpending, &s.DailyIncome, &s.CreatedAt); err != nil {
			return nil, fmt.Errorf("scanning daily snapshot: %w", err)
		}
		snapshots = append(snapshots, s)
	}
	return snapshots, rows.Err()
}

// GetAccountRange returns account snapshots for a specific account between two dates.
// Used for per-account sparklines.
func (r *SnapshotRepo) GetAccountRange(ctx context.Context, accountID string, from, to time.Time) ([]models.AccountSnapshot, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, date, account_id, balance, created_at
		FROM account_snapshots
		WHERE account_id = $1 AND date >= $2 AND date <= $3
		ORDER BY date ASC
	`, accountID, from, to)
	if err != nil {
		return nil, fmt.Errorf("querying account snapshots: %w", err)
	}
	defer rows.Close()

	var snapshots []models.AccountSnapshot
	for rows.Next() {
		var s models.AccountSnapshot
		if err := rows.Scan(&s.ID, &s.Date, &s.AccountID, &s.Balance, &s.CreatedAt); err != nil {
			return nil, fmt.Errorf("scanning account snapshot: %w", err)
		}
		snapshots = append(snapshots, s)
	}
	return snapshots, rows.Err()
}

// Exists checks if a daily snapshot already exists for the given date.
func (r *SnapshotRepo) Exists(ctx context.Context, date time.Time) (bool, error) {
	var exists bool
	err := r.db.QueryRowContext(ctx, `
		SELECT EXISTS(SELECT 1 FROM daily_snapshots WHERE date = $1)
	`, date).Scan(&exists)
	return exists, err
}

// GetLatestDate returns the most recent snapshot date, or zero time if none exist.
func (r *SnapshotRepo) GetLatestDate(ctx context.Context) (time.Time, error) {
	var date sql.NullTime
	err := r.db.QueryRowContext(ctx, `
		SELECT MAX(date) FROM daily_snapshots
	`).Scan(&date)
	if err != nil {
		return time.Time{}, err
	}
	if !date.Valid {
		return time.Time{}, nil
	}
	return date.Time, nil
}

// GetDailySpending returns the sum of expense amounts for a given date.
// Queries the transactions table directly.
func (r *SnapshotRepo) GetDailySpending(ctx context.Context, date time.Time) (float64, error) {
	var total sql.NullFloat64
	err := r.db.QueryRowContext(ctx, `
		SELECT SUM(amount) FROM transactions
		WHERE date::date = $1::date AND type = 'expense'
	`, date).Scan(&total)
	if err != nil {
		return 0, err
	}
	if !total.Valid {
		return 0, nil
	}
	return total.Float64, nil
}

// GetDailyIncome returns the sum of income amounts for a given date.
func (r *SnapshotRepo) GetDailyIncome(ctx context.Context, date time.Time) (float64, error) {
	var total sql.NullFloat64
	err := r.db.QueryRowContext(ctx, `
		SELECT SUM(amount) FROM transactions
		WHERE date::date = $1::date AND type = 'income'
	`, date).Scan(&total)
	if err != nil {
		return 0, err
	}
	if !total.Valid {
		return 0, nil
	}
	return total.Float64, nil
}

// GetBalanceDeltaAfterDate returns the sum of balance_delta for an account
// for transactions dated AFTER the given date. Used by backfill to compute
// historical balances: balance_on_date = current_balance - delta_after_date.
func (r *SnapshotRepo) GetBalanceDeltaAfterDate(ctx context.Context, accountID string, date time.Time) (float64, error) {
	var total sql.NullFloat64
	err := r.db.QueryRowContext(ctx, `
		SELECT SUM(balance_delta) FROM transactions
		WHERE account_id = $1 AND date::date > $2::date
	`, accountID, date).Scan(&total)
	if err != nil {
		return 0, err
	}
	if !total.Valid {
		return 0, nil
	}
	return total.Float64, nil
}
