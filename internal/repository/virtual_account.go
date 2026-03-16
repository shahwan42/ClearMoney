// Package repository — virtual_account.go provides database operations for virtual accounts
// (envelope budgeting system).
//
// Virtual accounts are "virtual envelopes" that let users earmark money for goals
// (e.g., "Emergency Fund", "Vacation", "New Laptop"). Money isn't physically
// moved between accounts — instead, transactions are allocated to virtual accounts, and
// each virtual account tracks its virtual balance.
//
// Two tables are involved:
//   - virtual_accounts: the virtual account itself (name, target, balance, icon, color)
//   - virtual_account_allocations: links transactions to virtual accounts with amounts
//
// The current_balance is a cached sum of allocations. RecalculateBalance()
// recomputes it from scratch using a subquery — like a denormalized counter cache.
//
//   Laravel analogy:  A VirtualAccount model with a many-to-many pivot table to transactions
//                     (virtual_account_allocations), plus a cached counter.
//   Django analogy:   VirtualAccount model with a ManyToManyField through='VirtualAccountAllocation',
//                     and a denormalized current_balance updated via signals or F() expressions.
//
// Uses PostgreSQL UPSERT (ON CONFLICT DO UPDATE) in the Allocate method for idempotency.
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/lib/pq"
)

// VirtualAccountRepo handles database operations for virtual_accounts and their allocations.
type VirtualAccountRepo struct {
	db *sql.DB
}

// NewVirtualAccountRepo creates a new VirtualAccountRepo with the given database connection pool.
func NewVirtualAccountRepo(db *sql.DB) *VirtualAccountRepo {
	return &VirtualAccountRepo{db: db}
}

// GetAll returns all non-archived virtual accounts, ordered by display_order.
func (r *VirtualAccountRepo) GetAll(ctx context.Context, userID string) ([]models.VirtualAccount, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, name, target_amount, current_balance, icon, color,
		       is_archived, exclude_from_net_worth, display_order, account_id, created_at, updated_at
		FROM virtual_accounts
		WHERE is_archived = false AND user_id = $1
		ORDER BY display_order, created_at
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanVirtualAccounts(rows)
}

// GetAllIncludingArchived returns all virtual accounts (for settings/management).
func (r *VirtualAccountRepo) GetAllIncludingArchived(ctx context.Context, userID string) ([]models.VirtualAccount, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, name, target_amount, current_balance, icon, color,
		       is_archived, exclude_from_net_worth, display_order, account_id, created_at, updated_at
		FROM virtual_accounts
		WHERE user_id = $1
		ORDER BY display_order, created_at
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanVirtualAccounts(rows)
}

// GetByID returns a single virtual account by ID.
func (r *VirtualAccountRepo) GetByID(ctx context.Context, userID string, id string) (models.VirtualAccount, error) {
	var a models.VirtualAccount
	err := r.db.QueryRowContext(ctx, `
		SELECT id, name, target_amount, current_balance, icon, color,
		       is_archived, exclude_from_net_worth, display_order, account_id, created_at, updated_at
		FROM virtual_accounts WHERE id = $1 AND user_id = $2
	`, id, userID).Scan(&a.ID, &a.Name, &a.TargetAmount, &a.CurrentBalance, &a.Icon, &a.Color,
		&a.IsArchived, &a.ExcludeFromNetWorth, &a.DisplayOrder, &a.AccountID, &a.CreatedAt, &a.UpdatedAt)
	return a, err
}

// Create inserts a new virtual account and returns the created record.
func (r *VirtualAccountRepo) Create(ctx context.Context, userID string, a models.VirtualAccount) (models.VirtualAccount, error) {
	a.UserID = userID
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO virtual_accounts (user_id, name, target_amount, icon, color, display_order, account_id, exclude_from_net_worth)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING id, name, target_amount, current_balance, icon, color,
		          is_archived, exclude_from_net_worth, display_order, account_id, created_at, updated_at
	`, userID, a.Name, a.TargetAmount, a.Icon, a.Color, a.DisplayOrder, a.AccountID, a.ExcludeFromNetWorth).Scan(
		&a.ID, &a.Name, &a.TargetAmount, &a.CurrentBalance, &a.Icon, &a.Color,
		&a.IsArchived, &a.ExcludeFromNetWorth, &a.DisplayOrder, &a.AccountID, &a.CreatedAt, &a.UpdatedAt)
	return a, err
}

// Update modifies a virtual account's name, target, icon, color, and order.
func (r *VirtualAccountRepo) Update(ctx context.Context, userID string, a models.VirtualAccount) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE virtual_accounts
		SET name = $2, target_amount = $3, icon = $4, color = $5,
		    display_order = $6, account_id = $7, exclude_from_net_worth = $8, updated_at = NOW()
		WHERE id = $1 AND user_id = $9
	`, a.ID, a.Name, a.TargetAmount, a.Icon, a.Color, a.DisplayOrder, a.AccountID, a.ExcludeFromNetWorth, userID)
	return err
}

// Archive soft-deletes a virtual account (keeps data for history, hides from active UI).
// Unlike hard delete, archived virtual accounts preserve their allocations and can be restored.
//   Laravel:  $account->update(['is_archived' => true]);  // like SoftDeletes
//   Django:   account.is_archived = True; account.save()
func (r *VirtualAccountRepo) Archive(ctx context.Context, userID string, id string) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE virtual_accounts SET is_archived = true, updated_at = NOW() WHERE id = $1 AND user_id = $2
	`, id, userID)
	return err
}

// Unarchive restores an archived virtual account.
func (r *VirtualAccountRepo) Unarchive(ctx context.Context, userID string, id string) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE virtual_accounts SET is_archived = false, updated_at = NOW() WHERE id = $1 AND user_id = $2
	`, id, userID)
	return err
}

// RecalculateBalance recomputes a virtual account's balance from its allocations.
// Called after adding/removing allocations to keep the cached balance in sync.
//
// This uses a correlated subquery: the inner SELECT SUM() runs for the
// specific virtual account, and the result is SET into the current_balance column.
// COALESCE(..., 0) handles the case where there are no allocations (SUM returns NULL).
//
// This is a "denormalized counter cache" pattern:
//   Laravel:  Like withCount() or a manually maintained counter_cache column
//   Django:   Like calling account.allocations.aggregate(Sum('amount')) and saving it
//
// The $1 parameter is used in BOTH the subquery WHERE and the outer WHERE — PostgreSQL
// reuses the same placeholder value in both positions.
func (r *VirtualAccountRepo) RecalculateBalance(ctx context.Context, userID string, accountID string) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE virtual_accounts
		SET current_balance = COALESCE((
			SELECT SUM(amount) FROM virtual_account_allocations WHERE virtual_account_id = $1
		), 0),
		updated_at = NOW()
		WHERE id = $1 AND user_id = $2
	`, accountID, userID)
	return err
}

// --- Allocation operations (the pivot/junction table) ---

// Allocate links a transaction to a virtual account with the given amount.
//
// Uses UPSERT (INSERT ... ON CONFLICT DO UPDATE) so calling Allocate twice
// for the same transaction+virtual account pair updates the amount instead of erroring.
// The partial unique index idx_vaa_tx_va_unique (WHERE transaction_id IS NOT NULL) triggers ON CONFLICT.
//
//   Laravel:  $account->transactions()->syncWithoutDetaching([$txId => ['amount' => $amount]])
//   Django:   VirtualAccountAllocation.objects.update_or_create(transaction=tx, virtual_account=account, defaults={'amount': amount})
func (r *VirtualAccountRepo) Allocate(ctx context.Context, userID string, alloc models.VirtualAccountAllocation) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO virtual_account_allocations (transaction_id, virtual_account_id, amount)
		VALUES ($1, $2, $3)
		ON CONFLICT (transaction_id, virtual_account_id) WHERE transaction_id IS NOT NULL
		DO UPDATE SET amount = EXCLUDED.amount
	`, alloc.TransactionID, alloc.VirtualAccountID, alloc.Amount)
	return err
}

// DirectAllocate creates a direct allocation (no transaction) to earmark existing funds.
// Used from the virtual account detail page for envelope budgeting contributions/withdrawals.
func (r *VirtualAccountRepo) DirectAllocate(ctx context.Context, userID string, alloc models.VirtualAccountAllocation) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO virtual_account_allocations (virtual_account_id, amount, note, allocated_at)
		VALUES ($1, $2, $3, $4)
	`, alloc.VirtualAccountID, alloc.Amount, alloc.Note, alloc.AllocatedAt)
	return err
}

// Deallocate removes a transaction's allocation from a virtual account.
func (r *VirtualAccountRepo) Deallocate(ctx context.Context, userID string, transactionID, accountID string) error {
	_, err := r.db.ExecContext(ctx, `
		DELETE FROM virtual_account_allocations
		WHERE transaction_id = $1 AND virtual_account_id = $2
	`, transactionID, accountID)
	return err
}

// GetAllocationsForAccount returns all allocations for a virtual account, most recent first.
// Uses LEFT JOIN so both transaction-linked and direct allocations appear.
func (r *VirtualAccountRepo) GetAllocationsForAccount(ctx context.Context, userID string, accountID string, limit int) ([]models.VirtualAccountAllocation, error) {
	query := `
		SELECT a.id, a.transaction_id, a.virtual_account_id, a.amount,
		       a.note, a.allocated_at, a.created_at
		FROM virtual_account_allocations a
		LEFT JOIN transactions t ON a.transaction_id = t.id
		JOIN virtual_accounts va ON a.virtual_account_id = va.id
		WHERE a.virtual_account_id = $1 AND va.user_id = $2
		ORDER BY COALESCE(t.date, a.allocated_at) DESC, a.created_at DESC
	`
	if limit > 0 {
		query += " LIMIT $3"
	}

	var rows *sql.Rows
	var err error
	if limit > 0 {
		rows, err = r.db.QueryContext(ctx, query, accountID, userID, limit)
	} else {
		rows, err = r.db.QueryContext(ctx, query, accountID, userID)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var allocs []models.VirtualAccountAllocation
	for rows.Next() {
		var a models.VirtualAccountAllocation
		if err := rows.Scan(&a.ID, &a.TransactionID, &a.VirtualAccountID, &a.Amount,
			&a.Note, &a.AllocatedAt, &a.CreatedAt); err != nil {
			return nil, err
		}
		allocs = append(allocs, a)
	}
	return allocs, rows.Err()
}

// GetAllocationsForTransaction returns all virtual account allocations for a transaction.
func (r *VirtualAccountRepo) GetAllocationsForTransaction(ctx context.Context, userID string, txID string) ([]models.VirtualAccountAllocation, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT a.id, a.transaction_id, a.virtual_account_id, a.amount, a.note, a.allocated_at, a.created_at
		FROM virtual_account_allocations a
		JOIN virtual_accounts va ON a.virtual_account_id = va.id
		WHERE a.transaction_id = $1 AND va.user_id = $2
		ORDER BY a.created_at
	`, txID, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var allocs []models.VirtualAccountAllocation
	for rows.Next() {
		var a models.VirtualAccountAllocation
		if err := rows.Scan(&a.ID, &a.TransactionID, &a.VirtualAccountID, &a.Amount,
			&a.Note, &a.AllocatedAt, &a.CreatedAt); err != nil {
			return nil, err
		}
		allocs = append(allocs, a)
	}
	return allocs, rows.Err()
}

// GetTransactionsForAccount returns full transaction records allocated to a virtual account.
// Uses JOIN through the allocation pivot table to find associated transactions.
// The SELECT column list matches TransactionRepo's queryTransactions for compatibility.
//
//   Laravel:  $account->transactions()->orderByDesc('date')->limit($limit)->get()
//   Django:   Transaction.objects.filter(account_allocations__virtual_account_id=account_id).order_by('-date')[:limit]
func (r *VirtualAccountRepo) GetTransactionsForAccount(ctx context.Context, userID string, accountID string, limit int) ([]models.Transaction, error) {
	query := `
		SELECT t.id, t.type, t.amount, t.currency, t.account_id,
		       t.counter_account_id, t.category_id, t.date, t.time,
		       t.note, t.tags, t.exchange_rate, t.counter_amount,
		       t.fee_amount, t.fee_account_id, t.person_id, t.linked_transaction_id,
		       t.recurring_rule_id, t.balance_delta,
		       t.created_at, t.updated_at
		FROM transactions t
		JOIN virtual_account_allocations a ON t.id = a.transaction_id
		JOIN virtual_accounts va ON a.virtual_account_id = va.id
		WHERE a.virtual_account_id = $1 AND va.user_id = $2
		ORDER BY t.date DESC, t.created_at DESC
	`
	if limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", limit)
	}

	rows, err := r.db.QueryContext(ctx, query, accountID, userID)
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

// scanVirtualAccounts scans multiple virtual account rows into a slice.
// This is a standalone function (not a method) because it doesn't need the repo's db field.
// It accepts *sql.Rows and returns the scanned results — a DRY helper shared by
// GetAll and GetAllIncludingArchived.
//
// Note: this is a package-level function (lowercase = unexported), not a method
// on VirtualAccountRepo. In Go, standalone helpers are common when they don't need receiver state.
func scanVirtualAccounts(rows *sql.Rows) ([]models.VirtualAccount, error) {
	var accounts []models.VirtualAccount
	for rows.Next() {
		var a models.VirtualAccount
		if err := rows.Scan(&a.ID, &a.Name, &a.TargetAmount, &a.CurrentBalance,
			&a.Icon, &a.Color, &a.IsArchived, &a.ExcludeFromNetWorth, &a.DisplayOrder,
			&a.AccountID, &a.CreatedAt, &a.UpdatedAt); err != nil {
			return nil, err
		}
		accounts = append(accounts, a)
	}
	return accounts, rows.Err()
}

// CountAllocationsForAccount returns how many allocations a virtual account has.
// Used to check before hard-deleting: a virtual account with allocations should be
// archived (soft-deleted) instead of hard-deleted to preserve history.
//
// COUNT(*) always returns a value (0 for no rows), so no NullInt64 needed.
//   Laravel:  $account->allocations()->count()
//   Django:   account.allocations.count()
func (r *VirtualAccountRepo) CountAllocationsForAccount(ctx context.Context, userID string, accountID string) (int, error) {
	var count int
	err := r.db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM virtual_account_allocations a
		JOIN virtual_accounts va ON a.virtual_account_id = va.id
		WHERE a.virtual_account_id = $1 AND va.user_id = $2
	`, accountID, userID).Scan(&count)
	return count, err
}

// GetByAccountID returns non-archived virtual accounts linked to a specific bank account.
func (r *VirtualAccountRepo) GetByAccountID(ctx context.Context, userID string, accountID string) ([]models.VirtualAccount, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, name, target_amount, current_balance, icon, color,
		       is_archived, exclude_from_net_worth, display_order, account_id, created_at, updated_at
		FROM virtual_accounts
		WHERE account_id = $1 AND is_archived = false AND user_id = $2
		ORDER BY display_order, created_at
	`, accountID, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanVirtualAccounts(rows)
}

// GetExcludedBalanceByAccountID returns total excluded VA balance for a bank account.
// Used to compute per-account "net balance" (actual balance - money held for others).
func (r *VirtualAccountRepo) GetExcludedBalanceByAccountID(ctx context.Context, userID string, accountID string) (float64, error) {
	var total float64
	err := r.db.QueryRowContext(ctx, `
		SELECT COALESCE(SUM(current_balance), 0)
		FROM virtual_accounts
		WHERE account_id = $1 AND exclude_from_net_worth = true AND is_archived = false AND user_id = $2
	`, accountID, userID).Scan(&total)
	return total, err
}

// GetTotalExcludedBalance returns the total balance across all excluded VAs.
// Used to adjust net worth on the dashboard — subtracting money held for others.
func (r *VirtualAccountRepo) GetTotalExcludedBalance(ctx context.Context, userID string) (float64, error) {
	var total float64
	err := r.db.QueryRowContext(ctx, `
		SELECT COALESCE(SUM(current_balance), 0)
		FROM virtual_accounts
		WHERE exclude_from_net_worth = true AND is_archived = false AND user_id = $1
	`, userID).Scan(&total)
	return total, err
}

// Delete removes a virtual account entirely (only if no allocations exist).
func (r *VirtualAccountRepo) Delete(ctx context.Context, userID string, id string) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM virtual_accounts WHERE id = $1 AND user_id = $2`, id, userID)
	return err
}
