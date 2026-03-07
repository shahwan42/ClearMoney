// Package jobs contains background tasks like balance reconciliation.
// Similar to Laravel's scheduled jobs or Django management commands.
package jobs

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"math"
)

// Discrepancy holds the details of a balance mismatch for an account.
type Discrepancy struct {
	AccountID       string
	AccountName     string
	CachedBalance   float64
	ExpectedBalance float64
	Difference      float64
}

// ReconcileBalances recomputes all account balances from transaction history,
// compares to cached current_balance, and returns any discrepancies.
//
// Expected balance = initial_balance + SUM(balance_delta) for all transactions.
// The balance_delta column stores the actual balance impact of each transaction,
// making reconciliation straightforward regardless of transaction type.
//
// autoFix: if true, update current_balance to match the computed value.
func ReconcileBalances(ctx context.Context, db *sql.DB, autoFix bool) ([]Discrepancy, error) {
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
	defer rows.Close()

	var discrepancies []Discrepancy
	for rows.Next() {
		var id, name string
		var cached, expected float64
		if err := rows.Scan(&id, &name, &cached, &expected); err != nil {
			return nil, fmt.Errorf("scanning row: %w", err)
		}

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
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterating rows: %w", err)
	}

	if autoFix && len(discrepancies) > 0 {
		for _, d := range discrepancies {
			_, err := db.ExecContext(ctx, `
				UPDATE accounts SET current_balance = $2, updated_at = now() WHERE id = $1
			`, d.AccountID, d.ExpectedBalance)
			if err != nil {
				log.Printf("WARNING: failed to fix balance for %s (%s): %v", d.AccountID, d.AccountName, err)
			} else {
				log.Printf("FIXED: %s (%s) balance %.2f → %.2f", d.AccountID, d.AccountName, d.CachedBalance, d.ExpectedBalance)
			}
		}
	}

	return discrepancies, nil
}
