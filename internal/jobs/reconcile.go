// Package jobs contains background tasks that run on startup or on a schedule.
//
// # Laravel/Django Comparison
//
// These are the Go equivalents of:
//   - Laravel:  Scheduled jobs (app/Console/Kernel.php), Artisan commands (php artisan),
//               or queued jobs (app/Jobs/). In Laravel you'd register them with
//               $schedule->command('reconcile:balances')->daily()
//   - Django:   Management commands (python manage.py reconcile_balances) or
//               Celery tasks (@shared_task). Django management commands live in
//               management/commands/ — Go jobs live in internal/jobs/.
//
// Key difference: Go doesn't have a built-in task scheduler like Laravel's Kernel
// or Celery. Instead, these jobs are called directly from main.go on startup,
// and can also be invoked via Makefile targets (e.g., `make reconcile`).
//
// See: https://pkg.go.dev/database/sql (Go's database abstraction, similar to PDO)
package jobs

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
	"math"
)

// Discrepancy holds the details of a balance mismatch for an account.
// This is a plain struct (Go's equivalent of a DTO/Value Object). Unlike Laravel's
// Eloquent models or Django's Model instances, this struct has no database methods
// attached — it's purely for carrying data between functions.
type Discrepancy struct {
	AccountID       string
	AccountName     string
	CachedBalance   float64 // What the accounts table currently says
	ExpectedBalance float64 // What the transaction history says it should be
	Difference      float64 // ExpectedBalance - CachedBalance
}

// ReconcileBalances recomputes all account balances from transaction history,
// compares to the cached current_balance, and returns any discrepancies.
//
// # The Reconciliation Algorithm
//
// Each account has two sources of truth for its balance:
//   1. current_balance (cached/denormalized) — updated incrementally on each transaction
//   2. initial_balance + SUM(balance_delta) — computed from the full transaction history
//
// If these two values diverge (due to bugs, race conditions, manual DB edits, etc.),
// we have a discrepancy. This job detects and optionally fixes those mismatches.
//
// The formula: expected_balance = initial_balance + SUM(balance_delta)
//
// The balance_delta column stores the actual balance impact of each transaction,
// which varies by type:
//   - expense:  balance_delta = -amount (money leaves the account)
//   - income:   balance_delta = +amount (money enters the account)
//   - transfer: balance_delta = -amount on source, +amount on destination
//
// This is similar to ledger reconciliation in accounting — comparing the running
// balance to an independently computed total. In Laravel, you might do this with
// Account::all()->each(fn($a) => $a->reconcile()) using Eloquent.
//
// # Parameters
//
//   - ctx:     context for cancellation/timeouts (like Laravel's job timeout)
//   - db:      raw database connection (Go's *sql.DB, similar to Laravel's DB facade)
//   - autoFix: if true, UPDATE current_balance to match the computed value
//
// # SQL Pattern: Correlated Subquery
//
// The query uses a correlated subquery — the inner SELECT references the outer
// table (a.id). PostgreSQL evaluates the inner query once per row of the outer
// query. COALESCE(..., 0) handles accounts with zero transactions (SUM returns
// NULL for empty sets, which we convert to 0).
//
// See: https://pkg.go.dev/database/sql#DB.QueryContext
// See: https://pkg.go.dev/fmt#Errorf (the %w verb wraps errors for errors.Is/As)
func ReconcileBalances(ctx context.Context, db *sql.DB, autoFix bool) ([]Discrepancy, error) {
	// db.QueryContext returns *sql.Rows, a cursor over the result set.
	// This is similar to Laravel's DB::select() or Django's raw SQL with cursor.
	// IMPORTANT: rows must be closed (see defer below) or you leak DB connections.
	rows, err := db.QueryContext(ctx, `
		SELECT
			a.id,
			a.name,
			a.current_balance,
			a.initial_balance + COALESCE((
				SELECT SUM(t.balance_delta)
				FROM transactions t
				WHERE t.account_id = a.id
			), 0) AS expected_balance
		FROM accounts a
		ORDER BY a.name
	`)
	if err != nil {
		return nil, fmt.Errorf("querying balances: %w", err)
	}
	// defer rows.Close() ensures the cursor is closed when this function returns,
	// even if we return early due to an error. This is Go's equivalent of a
	// try/finally block. Always defer Close() right after a successful open.
	// See: https://go.dev/blog/defer-panic-and-recover
	defer rows.Close()

	// Go uses nil slices (not empty slices) by default. A nil slice is perfectly
	// valid — len(nil) is 0, and append works on nil. This is more memory-efficient
	// than pre-allocating when most runs will have 0 discrepancies.
	var discrepancies []Discrepancy

	// rows.Next() advances the cursor. The loop pattern is:
	//   for rows.Next() { rows.Scan(&vars...) }
	// This is like PDO::fetch() in a while loop, or Django's cursor.fetchone().
	for rows.Next() {
		var id, name string
		var cached, expected float64
		// rows.Scan populates variables by pointer — Go's way of "returning"
		// multiple values from a database row. The order must match the SELECT columns.
		if err := rows.Scan(&id, &name, &cached, &expected); err != nil {
			return nil, fmt.Errorf("scanning row: %w", err)
		}

		// Use a tolerance of 0.005 to avoid floating-point noise.
		// Since we store monetary values as NUMERIC(15,2) in PostgreSQL, differences
		// smaller than half a cent are just floating-point representation artifacts.
		diff := expected - cached
		if math.Abs(diff) > 0.005 {
			discrepancies = append(discrepancies, Discrepancy{
				AccountID:       id,
				AccountName:     name,
				CachedBalance:   cached,
				ExpectedBalance: expected,
				Difference:      diff,
			})
		}
	}
	// rows.Err() catches errors that occurred during iteration (e.g., network
	// failure mid-stream). Always check this after the loop — it's a common
	// Go gotcha that Laravel/Django developers won't encounter (ORMs handle this).
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterating rows: %w", err)
	}

	// Auto-fix: update cached balances to match computed values.
	// db.ExecContext is for write queries (INSERT/UPDATE/DELETE) — similar to
	// Laravel's DB::update() or Django's cursor.execute() for DML statements.
	// $1, $2 are PostgreSQL parameterized placeholders (prevents SQL injection).
	// MySQL uses ?, Laravel uses ?, Django uses %s — PostgreSQL uses $N.
	if autoFix && len(discrepancies) > 0 {
		for _, d := range discrepancies {
			_, err := db.ExecContext(ctx, `
				UPDATE accounts SET current_balance = $2, updated_at = now() WHERE id = $1
			`, d.AccountID, d.ExpectedBalance)
			if err != nil {
				slog.Warn("failed to fix balance", "account_id", d.AccountID, "account", d.AccountName, "error", err)
			} else {
				slog.Info("fixed balance", "account_id", d.AccountID, "account", d.AccountName, "from", d.CachedBalance, "to", d.ExpectedBalance)
			}
		}
	}

	return discrepancies, nil
}
