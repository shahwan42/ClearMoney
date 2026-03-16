// Package repository — SnapshotRepo handles CRUD for daily balance snapshots.
//
// Snapshots capture a point-in-time record of account balances and net worth.
// They power sparkline charts on the dashboard and account detail pages.
// Two tables are involved:
//   - daily_snapshots: one row per day with net worth and spending totals
//   - account_snapshots: one row per day per account with the account balance
//
// Uses PostgreSQL UPSERT (INSERT ... ON CONFLICT DO UPDATE) so snapshots are
// idempotent — running the snapshot job twice for the same day safely updates
// rather than creating duplicates. This is a key pattern for background jobs.
//
//   Laravel analogy:  updateOrCreate() — finds by key, creates if missing, updates if exists
//   Django analogy:   update_or_create(date=date, defaults={...})
//   PostgreSQL:       INSERT ... ON CONFLICT (date) DO UPDATE SET ...
//
// See: https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT
package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
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
//
// This uses PostgreSQL's UPSERT pattern:
//   INSERT INTO ... VALUES (...)
//   ON CONFLICT (date) DO UPDATE SET column = EXCLUDED.column
//
// EXCLUDED is a special PostgreSQL keyword that refers to the row that WOULD have
// been inserted. So "SET net_worth_egp = EXCLUDED.net_worth_egp" means "use the
// new value we tried to insert".
//
//   Laravel:  DailySnapshot::updateOrCreate(['date' => $date], [...])
//   Django:   DailySnapshot.objects.update_or_create(date=date, defaults={...})
//
// The ON CONFLICT clause requires a UNIQUE constraint on the (date) column.
func (r *SnapshotRepo) UpsertDaily(ctx context.Context, userID string, snap models.DailySnapshot) error {
	snap.UserID = userID
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO daily_snapshots (user_id, date, net_worth_egp, net_worth_raw, exchange_rate, daily_spending, daily_income)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		ON CONFLICT (date, user_id) DO UPDATE SET
			net_worth_egp = EXCLUDED.net_worth_egp,
			net_worth_raw = EXCLUDED.net_worth_raw,
			exchange_rate = EXCLUDED.exchange_rate,
			daily_spending = EXCLUDED.daily_spending,
			daily_income = EXCLUDED.daily_income
	`, userID, snap.Date, snap.NetWorthEGP, snap.NetWorthRaw, snap.ExchangeRate,
		snap.DailySpending, snap.DailyIncome)
	if err != nil {
		return fmt.Errorf("upserting daily snapshot: %w", err)
	}
	return nil
}

// UpsertAccount creates or updates an account snapshot for the given date+account.
// Uses ON CONFLICT (date, account_id) DO UPDATE for idempotency.
// The UNIQUE constraint is on the compound key (date, account_id).
func (r *SnapshotRepo) UpsertAccount(ctx context.Context, userID string, snap models.AccountSnapshot) error {
	snap.UserID = userID
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO account_snapshots (user_id, date, account_id, balance)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (date, account_id) DO UPDATE SET
			balance = EXCLUDED.balance
	`, userID, snap.Date, snap.AccountID, snap.Balance)
	if err != nil {
		return fmt.Errorf("upserting account snapshot: %w", err)
	}
	return nil
}

// GetDailyRange returns daily snapshots between two dates (inclusive), ordered by date ASC.
// Used for sparklines: e.g., "last 30 days of net worth".
func (r *SnapshotRepo) GetDailyRange(ctx context.Context, userID string, from, to time.Time) ([]models.DailySnapshot, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, date, net_worth_egp, net_worth_raw, exchange_rate,
			daily_spending, daily_income, created_at
		FROM daily_snapshots
		WHERE date >= $1 AND date <= $2 AND user_id = $3
		ORDER BY date ASC
	`, from, to, userID)
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
func (r *SnapshotRepo) GetAccountRange(ctx context.Context, userID string, accountID string, from, to time.Time) ([]models.AccountSnapshot, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, date, account_id, balance, created_at
		FROM account_snapshots
		WHERE account_id = $1 AND date >= $2 AND date <= $3 AND user_id = $4
		ORDER BY date ASC
	`, accountID, from, to, userID)
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

// GetNetWorthByCurrency returns per-currency net worth history between two dates.
// Sums account_snapshots balances grouped by currency and date, returning a map
// keyed by currency code (e.g., "EGP", "USD") with a slice of daily totals.
func (r *SnapshotRepo) GetNetWorthByCurrency(ctx context.Context, userID string, from, to time.Time) (map[string][]float64, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT s.date, a.currency, SUM(s.balance) as total
		FROM account_snapshots s
		JOIN accounts a ON a.id = s.account_id
		WHERE s.date >= $1 AND s.date <= $2 AND s.user_id = $3
		GROUP BY s.date, a.currency
		ORDER BY s.date ASC
	`, from, to, userID)
	if err != nil {
		return nil, fmt.Errorf("querying net worth by currency: %w", err)
	}
	defer rows.Close()

	result := make(map[string][]float64)
	for rows.Next() {
		var date time.Time
		var currency string
		var total float64
		if err := rows.Scan(&date, &currency, &total); err != nil {
			return nil, fmt.Errorf("scanning net worth by currency: %w", err)
		}
		result[currency] = append(result[currency], total)
	}
	return result, rows.Err()
}

// Exists checks if a daily snapshot already exists for the given date.
//
// SELECT EXISTS(SELECT 1 FROM ... WHERE ...) is the most efficient existence check.
// PostgreSQL returns TRUE/FALSE directly — no need to count rows or fetch data.
// The inner `SELECT 1` doesn't fetch any columns; it just checks for row existence.
//
//   Laravel:  DailySnapshot::where('date', $date)->exists()
//   Django:   DailySnapshot.objects.filter(date=date).exists()
func (r *SnapshotRepo) Exists(ctx context.Context, userID string, date time.Time) (bool, error) {
	var exists bool
	err := r.db.QueryRowContext(ctx, `
		SELECT EXISTS(SELECT 1 FROM daily_snapshots WHERE date = $1 AND user_id = $2)
	`, date, userID).Scan(&exists)
	return exists, err
}

// GetLatestDate returns the most recent snapshot date, or zero time if none exist.
//
// MAX(date) returns NULL when the table is empty, so we use sql.NullTime.
// sql.NullTime is the time.Time equivalent of sql.NullFloat64 — it wraps a
// time.Time with a Valid bool to handle SQL NULL values.
//
// time.Time{} is Go's "zero value" for time (January 1, year 1, 00:00:00 UTC).
// We return it when there are no snapshots — callers check with date.IsZero().
// See: https://pkg.go.dev/database/sql#NullTime
func (r *SnapshotRepo) GetLatestDate(ctx context.Context, userID string) (time.Time, error) {
	var date sql.NullTime
	err := r.db.QueryRowContext(ctx, `
		SELECT MAX(date) FROM daily_snapshots WHERE user_id = $1
	`, userID).Scan(&date)
	if err != nil {
		return time.Time{}, err
	}
	if !date.Valid {
		return time.Time{}, nil
	}
	return date.Time, nil
}

// GetDailySpending returns the sum of expense amounts for a given date.
// Queries the transactions table directly (not the snapshots table).
//
// The `date::date = $1::date` casts both sides to PostgreSQL's DATE type,
// stripping any time component. This ensures we match the entire day regardless
// of whether the stored timestamp has hours/minutes.
//   PostgreSQL:  ::date is a type cast (shorthand for CAST(x AS DATE))
//   Laravel:     whereDate('date', $date) — Laravel generates DATE() function
//   Django:      filter(date__date=date) — Django uses __date lookup
func (r *SnapshotRepo) GetDailySpending(ctx context.Context, userID string, date time.Time) (float64, error) {
	var total sql.NullFloat64
	err := r.db.QueryRowContext(ctx, `
		SELECT SUM(amount) FROM transactions
		WHERE date::date = $1::date AND type = 'expense' AND user_id = $2
	`, date, userID).Scan(&total)
	if err != nil {
		return 0, err
	}
	if !total.Valid {
		return 0, nil
	}
	return total.Float64, nil
}

// GetDailyIncome returns the sum of income amounts for a given date.
func (r *SnapshotRepo) GetDailyIncome(ctx context.Context, userID string, date time.Time) (float64, error) {
	var total sql.NullFloat64
	err := r.db.QueryRowContext(ctx, `
		SELECT SUM(amount) FROM transactions
		WHERE date::date = $1::date AND type = 'income' AND user_id = $2
	`, date, userID).Scan(&total)
	if err != nil {
		return 0, err
	}
	if !total.Valid {
		return 0, nil
	}
	return total.Float64, nil
}

// GetBalanceDeltaAfterDate returns the sum of balance_delta for an account
// for transactions dated AFTER the given date.
//
// Used by the snapshot backfill job to compute historical balances:
//   balance_on_date = current_balance - sum_of_deltas_after_date
//
// This works because balance_delta records how much each transaction changed
// the account balance. By subtracting all changes after a date from the current
// balance, we reconstruct what the balance was on that date.
//
// Example: current_balance = 10000, sum of deltas after Jan 15 = 3000
//   → balance on Jan 15 was 10000 - 3000 = 7000
func (r *SnapshotRepo) GetBalanceDeltaAfterDate(ctx context.Context, userID string, accountID string, date time.Time) (float64, error) {
	var total sql.NullFloat64
	err := r.db.QueryRowContext(ctx, `
		SELECT SUM(balance_delta) FROM transactions
		WHERE account_id = $1 AND date::date > $2::date AND user_id = $3
	`, accountID, date, userID).Scan(&total)
	if err != nil {
		return 0, err
	}
	if !total.Valid {
		return 0, nil
	}
	return total.Float64, nil
}
