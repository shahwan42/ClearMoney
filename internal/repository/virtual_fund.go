// Package repository — virtual_fund.go provides database operations for virtual funds
// (envelope budgeting system).
//
// Virtual funds are "virtual envelopes" that let users earmark money for goals
// (e.g., "Emergency Fund", "Vacation", "New Laptop"). Money isn't physically
// moved between accounts — instead, transactions are allocated to funds, and
// each fund tracks its virtual balance.
//
// Two tables are involved:
//   - virtual_funds: the fund itself (name, target, balance, icon, color)
//   - transaction_fund_allocations: links transactions to funds with amounts
//
// The current_balance is a cached sum of allocations. RecalculateBalance()
// recomputes it from scratch using a subquery — like a denormalized counter cache.
//
//   Laravel analogy:  A VirtualFund model with a many-to-many pivot table to transactions
//                     (transaction_fund_allocations), plus a cached counter.
//   Django analogy:   VirtualFund model with a ManyToManyField through='FundAllocation',
//                     and a denormalized current_balance updated via signals or F() expressions.
//
// Uses PostgreSQL UPSERT (ON CONFLICT DO UPDATE) in the Allocate method for idempotency.
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/lib/pq"
)

// VirtualFundRepo handles database operations for virtual_funds and their allocations.
type VirtualFundRepo struct {
	db *sql.DB
}

// NewVirtualFundRepo creates a new VirtualFundRepo with the given database connection pool.
func NewVirtualFundRepo(db *sql.DB) *VirtualFundRepo {
	return &VirtualFundRepo{db: db}
}

// GetAll returns all non-archived virtual funds, ordered by display_order.
func (r *VirtualFundRepo) GetAll(ctx context.Context) ([]models.VirtualFund, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, name, target_amount, current_balance, icon, color,
		       is_archived, display_order, created_at, updated_at
		FROM virtual_funds
		WHERE is_archived = false
		ORDER BY display_order, created_at
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanFunds(rows)
}

// GetAllIncludingArchived returns all virtual funds (for settings/management).
func (r *VirtualFundRepo) GetAllIncludingArchived(ctx context.Context) ([]models.VirtualFund, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, name, target_amount, current_balance, icon, color,
		       is_archived, display_order, created_at, updated_at
		FROM virtual_funds
		ORDER BY display_order, created_at
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanFunds(rows)
}

// GetByID returns a single virtual fund by ID.
func (r *VirtualFundRepo) GetByID(ctx context.Context, id string) (models.VirtualFund, error) {
	var f models.VirtualFund
	err := r.db.QueryRowContext(ctx, `
		SELECT id, name, target_amount, current_balance, icon, color,
		       is_archived, display_order, created_at, updated_at
		FROM virtual_funds WHERE id = $1
	`, id).Scan(&f.ID, &f.Name, &f.TargetAmount, &f.CurrentBalance, &f.Icon, &f.Color,
		&f.IsArchived, &f.DisplayOrder, &f.CreatedAt, &f.UpdatedAt)
	return f, err
}

// Create inserts a new virtual fund and returns the created record.
func (r *VirtualFundRepo) Create(ctx context.Context, f models.VirtualFund) (models.VirtualFund, error) {
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO virtual_funds (name, target_amount, icon, color, display_order)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, name, target_amount, current_balance, icon, color,
		          is_archived, display_order, created_at, updated_at
	`, f.Name, f.TargetAmount, f.Icon, f.Color, f.DisplayOrder).Scan(
		&f.ID, &f.Name, &f.TargetAmount, &f.CurrentBalance, &f.Icon, &f.Color,
		&f.IsArchived, &f.DisplayOrder, &f.CreatedAt, &f.UpdatedAt)
	return f, err
}

// Update modifies a virtual fund's name, target, icon, color, and order.
func (r *VirtualFundRepo) Update(ctx context.Context, f models.VirtualFund) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE virtual_funds
		SET name = $2, target_amount = $3, icon = $4, color = $5,
		    display_order = $6, updated_at = NOW()
		WHERE id = $1
	`, f.ID, f.Name, f.TargetAmount, f.Icon, f.Color, f.DisplayOrder)
	return err
}

// Archive soft-deletes a virtual fund (keeps data for history, hides from active UI).
// Unlike hard delete, archived funds preserve their allocations and can be restored.
//   Laravel:  $fund->update(['is_archived' => true]);  // like SoftDeletes
//   Django:   fund.is_archived = True; fund.save()
func (r *VirtualFundRepo) Archive(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE virtual_funds SET is_archived = true, updated_at = NOW() WHERE id = $1
	`, id)
	return err
}

// Unarchive restores an archived virtual fund.
func (r *VirtualFundRepo) Unarchive(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE virtual_funds SET is_archived = false, updated_at = NOW() WHERE id = $1
	`, id)
	return err
}

// RecalculateBalance recomputes a fund's balance from its allocations.
// Called after adding/removing allocations to keep the cached balance in sync.
//
// This uses a correlated subquery: the inner SELECT SUM() runs for the
// specific fund, and the result is SET into the current_balance column.
// COALESCE(..., 0) handles the case where there are no allocations (SUM returns NULL).
//
// This is a "denormalized counter cache" pattern:
//   Laravel:  Like withCount() or a manually maintained counter_cache column
//   Django:   Like calling fund.allocations.aggregate(Sum('amount')) and saving it
//
// The $1 parameter is used in BOTH the subquery WHERE and the outer WHERE — PostgreSQL
// reuses the same placeholder value in both positions.
func (r *VirtualFundRepo) RecalculateBalance(ctx context.Context, fundID string) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE virtual_funds
		SET current_balance = COALESCE((
			SELECT SUM(amount) FROM transaction_fund_allocations WHERE virtual_fund_id = $1
		), 0),
		updated_at = NOW()
		WHERE id = $1
	`, fundID)
	return err
}

// --- Allocation operations (the pivot/junction table) ---

// Allocate links a transaction to a virtual fund with the given amount.
//
// Uses UPSERT (INSERT ... ON CONFLICT DO UPDATE) so calling Allocate twice
// for the same transaction+fund pair updates the amount instead of erroring.
// The UNIQUE constraint on (transaction_id, virtual_fund_id) triggers ON CONFLICT.
//
//   Laravel:  $fund->transactions()->syncWithoutDetaching([$txId => ['amount' => $amount]])
//   Django:   FundAllocation.objects.update_or_create(transaction=tx, fund=fund, defaults={'amount': amount})
func (r *VirtualFundRepo) Allocate(ctx context.Context, alloc models.FundAllocation) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO transaction_fund_allocations (transaction_id, virtual_fund_id, amount)
		VALUES ($1, $2, $3)
		ON CONFLICT (transaction_id, virtual_fund_id)
		DO UPDATE SET amount = EXCLUDED.amount
	`, alloc.TransactionID, alloc.VirtualFundID, alloc.Amount)
	return err
}

// Deallocate removes a transaction's allocation from a fund.
func (r *VirtualFundRepo) Deallocate(ctx context.Context, transactionID, fundID string) error {
	_, err := r.db.ExecContext(ctx, `
		DELETE FROM transaction_fund_allocations
		WHERE transaction_id = $1 AND virtual_fund_id = $2
	`, transactionID, fundID)
	return err
}

// GetAllocationsForFund returns all allocations for a fund, most recent first.
func (r *VirtualFundRepo) GetAllocationsForFund(ctx context.Context, fundID string, limit int) ([]models.FundAllocation, error) {
	query := `
		SELECT a.id, a.transaction_id, a.virtual_fund_id, a.amount, a.created_at
		FROM transaction_fund_allocations a
		JOIN transactions t ON a.transaction_id = t.id
		WHERE a.virtual_fund_id = $1
		ORDER BY t.date DESC, a.created_at DESC
	`
	if limit > 0 {
		query += " LIMIT $2"
	}

	var rows *sql.Rows
	var err error
	if limit > 0 {
		rows, err = r.db.QueryContext(ctx, query, fundID, limit)
	} else {
		rows, err = r.db.QueryContext(ctx, query, fundID)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var allocs []models.FundAllocation
	for rows.Next() {
		var a models.FundAllocation
		if err := rows.Scan(&a.ID, &a.TransactionID, &a.VirtualFundID, &a.Amount, &a.CreatedAt); err != nil {
			return nil, err
		}
		allocs = append(allocs, a)
	}
	return allocs, rows.Err()
}

// GetAllocationsForTransaction returns all fund allocations for a transaction.
func (r *VirtualFundRepo) GetAllocationsForTransaction(ctx context.Context, txID string) ([]models.FundAllocation, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, transaction_id, virtual_fund_id, amount, created_at
		FROM transaction_fund_allocations
		WHERE transaction_id = $1
		ORDER BY created_at
	`, txID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var allocs []models.FundAllocation
	for rows.Next() {
		var a models.FundAllocation
		if err := rows.Scan(&a.ID, &a.TransactionID, &a.VirtualFundID, &a.Amount, &a.CreatedAt); err != nil {
			return nil, err
		}
		allocs = append(allocs, a)
	}
	return allocs, rows.Err()
}

// GetTransactionsForFund returns full transaction records allocated to a fund.
// Uses JOIN through the allocation pivot table to find associated transactions.
// The SELECT column list matches TransactionRepo's queryTransactions for compatibility.
//
//   Laravel:  $fund->transactions()->orderByDesc('date')->limit($limit)->get()
//   Django:   Transaction.objects.filter(fund_allocations__virtual_fund_id=fund_id).order_by('-date')[:limit]
func (r *VirtualFundRepo) GetTransactionsForFund(ctx context.Context, fundID string, limit int) ([]models.Transaction, error) {
	query := `
		SELECT t.id, t.type, t.amount, t.currency, t.account_id,
		       t.counter_account_id, t.category_id, t.date, t.time,
		       t.note, t.tags, t.exchange_rate, t.counter_amount,
		       t.fee_amount, t.fee_account_id, t.person_id, t.linked_transaction_id,
		       t.recurring_rule_id, t.balance_delta,
		       t.created_at, t.updated_at
		FROM transactions t
		JOIN transaction_fund_allocations a ON t.id = a.transaction_id
		WHERE a.virtual_fund_id = $1
		ORDER BY t.date DESC, t.created_at DESC
	`
	if limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", limit)
	}

	rows, err := r.db.QueryContext(ctx, query, fundID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var txns []models.Transaction
	for rows.Next() {
		var tx models.Transaction
		if err := rows.Scan(
			&tx.ID, &tx.Type, &tx.Amount, &tx.Currency, &tx.AccountID,
			&tx.CounterAccountID, &tx.CategoryID, &tx.Date, &tx.Time,
			&tx.Note, pq.Array(&tx.Tags), &tx.ExchangeRate, &tx.CounterAmount,
			&tx.FeeAmount, &tx.FeeAccountID, &tx.PersonID, &tx.LinkedTransactionID,
			&tx.RecurringRuleID, &tx.BalanceDelta,
			&tx.CreatedAt, &tx.UpdatedAt,
		); err != nil {
			return nil, err
		}
		txns = append(txns, tx)
	}
	return txns, rows.Err()
}

// --- Helpers ---

// scanFunds scans multiple virtual fund rows into a slice.
// This is a standalone function (not a method) because it doesn't need the repo's db field.
// It accepts *sql.Rows and returns the scanned results — a DRY helper shared by
// GetAll and GetAllIncludingArchived.
//
// Note: this is a package-level function (lowercase = unexported), not a method
// on VirtualFundRepo. In Go, standalone helpers are common when they don't need receiver state.
func scanFunds(rows *sql.Rows) ([]models.VirtualFund, error) {
	var funds []models.VirtualFund
	for rows.Next() {
		var f models.VirtualFund
		if err := rows.Scan(&f.ID, &f.Name, &f.TargetAmount, &f.CurrentBalance,
			&f.Icon, &f.Color, &f.IsArchived, &f.DisplayOrder,
			&f.CreatedAt, &f.UpdatedAt); err != nil {
			return nil, err
		}
		funds = append(funds, f)
	}
	return funds, rows.Err()
}

// CountAllocationsForFund returns how many allocations a fund has.
// Used to check before hard-deleting: a fund with allocations should be
// archived (soft-deleted) instead of hard-deleted to preserve history.
//
// COUNT(*) always returns a value (0 for no rows), so no NullInt64 needed.
//   Laravel:  $fund->allocations()->count()
//   Django:   fund.allocations.count()
func (r *VirtualFundRepo) CountAllocationsForFund(ctx context.Context, fundID string) (int, error) {
	var count int
	err := r.db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM transaction_fund_allocations WHERE virtual_fund_id = $1
	`, fundID).Scan(&count)
	return count, err
}

// Delete removes a virtual fund entirely (only if no allocations exist).
func (r *VirtualFundRepo) Delete(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM virtual_funds WHERE id = $1`, id)
	return err
}

