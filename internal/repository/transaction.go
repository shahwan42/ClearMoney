package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/lib/pq"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// TransactionRepo handles database operations for transactions.
type TransactionRepo struct {
	db *sql.DB
}

func NewTransactionRepo(db *sql.DB) *TransactionRepo {
	return &TransactionRepo{db: db}
}

// Create inserts a new transaction.
// Note: This does NOT update account balances — that's the service's job
// inside a database transaction (see TransactionService.Create).
func (r *TransactionRepo) Create(ctx context.Context, tx models.Transaction) (models.Transaction, error) {
	if tx.Date.IsZero() {
		tx.Date = time.Now()
	}

	err := r.db.QueryRowContext(ctx, `
		INSERT INTO transactions (type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
		RETURNING id, created_at, updated_at
	`, tx.Type, tx.Amount, tx.Currency, tx.AccountID, tx.CounterAccountID,
		tx.CategoryID, tx.Date, tx.Time, tx.Note, pq.Array(tx.Tags),
		tx.ExchangeRate, tx.CounterAmount, tx.FeeAmount, tx.FeeAccountID,
		tx.PersonID, tx.LinkedTransactionID, tx.IsBuildingFund, tx.RecurringRuleID,
		tx.BalanceDelta,
	).Scan(&tx.ID, &tx.CreatedAt, &tx.UpdatedAt)

	if err != nil {
		return models.Transaction{}, fmt.Errorf("inserting transaction: %w", err)
	}
	return tx, nil
}

// CreateTx inserts a transaction within an existing database transaction.
// Used by the service layer when we need atomicity (e.g., insert + balance update).
func (r *TransactionRepo) CreateTx(ctx context.Context, dbTx *sql.Tx, tx models.Transaction) (models.Transaction, error) {
	if tx.Date.IsZero() {
		tx.Date = time.Now()
	}

	err := dbTx.QueryRowContext(ctx, `
		INSERT INTO transactions (type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
		RETURNING id, created_at, updated_at
	`, tx.Type, tx.Amount, tx.Currency, tx.AccountID, tx.CounterAccountID,
		tx.CategoryID, tx.Date, tx.Time, tx.Note, pq.Array(tx.Tags),
		tx.ExchangeRate, tx.CounterAmount, tx.FeeAmount, tx.FeeAccountID,
		tx.PersonID, tx.LinkedTransactionID, tx.IsBuildingFund, tx.RecurringRuleID,
		tx.BalanceDelta,
	).Scan(&tx.ID, &tx.CreatedAt, &tx.UpdatedAt)

	if err != nil {
		return models.Transaction{}, fmt.Errorf("inserting transaction: %w", err)
	}
	return tx, nil
}

// GetByID retrieves a single transaction.
func (r *TransactionRepo) GetByID(ctx context.Context, id string) (models.Transaction, error) {
	var tx models.Transaction
	err := r.db.QueryRowContext(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE id = $1
	`, id).Scan(
		&tx.ID, &tx.Type, &tx.Amount, &tx.Currency, &tx.AccountID,
		&tx.CounterAccountID, &tx.CategoryID, &tx.Date, &tx.Time,
		&tx.Note, pq.Array(&tx.Tags), &tx.ExchangeRate, &tx.CounterAmount,
		&tx.FeeAmount, &tx.FeeAccountID, &tx.PersonID, &tx.LinkedTransactionID,
		&tx.IsBuildingFund, &tx.RecurringRuleID, &tx.BalanceDelta, &tx.CreatedAt, &tx.UpdatedAt,
	)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("getting transaction: %w", err)
	}
	return tx, nil
}

// GetRecent retrieves the most recent transactions across all accounts.
func (r *TransactionRepo) GetRecent(ctx context.Context, limit int) ([]models.Transaction, error) {
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions ORDER BY date DESC, created_at DESC LIMIT $1
	`, limit)
}

// GetByAccount retrieves transactions for a specific account.
func (r *TransactionRepo) GetByAccount(ctx context.Context, accountID string, limit int) ([]models.Transaction, error) {
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE account_id = $1
		ORDER BY date DESC, created_at DESC LIMIT $2
	`, accountID, limit)
}

// Update modifies a transaction's editable fields.
func (r *TransactionRepo) Update(ctx context.Context, tx models.Transaction) (models.Transaction, error) {
	err := r.db.QueryRowContext(ctx, `
		UPDATE transactions SET
			type = $2, amount = $3, currency = $4, category_id = $5,
			note = $6, date = $7, updated_at = now()
		WHERE id = $1
		RETURNING id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
	`, tx.ID, tx.Type, tx.Amount, tx.Currency, tx.CategoryID,
		tx.Note, tx.Date,
	).Scan(
		&tx.ID, &tx.Type, &tx.Amount, &tx.Currency, &tx.AccountID,
		&tx.CounterAccountID, &tx.CategoryID, &tx.Date, &tx.Time,
		&tx.Note, pq.Array(&tx.Tags), &tx.ExchangeRate, &tx.CounterAmount,
		&tx.FeeAmount, &tx.FeeAccountID, &tx.PersonID, &tx.LinkedTransactionID,
		&tx.IsBuildingFund, &tx.RecurringRuleID, &tx.BalanceDelta, &tx.CreatedAt, &tx.UpdatedAt,
	)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("updating transaction: %w", err)
	}
	return tx, nil
}

// UpdateTx modifies a transaction within an existing database transaction.
func (r *TransactionRepo) UpdateTx(ctx context.Context, dbTx *sql.Tx, tx models.Transaction) (models.Transaction, error) {
	err := dbTx.QueryRowContext(ctx, `
		UPDATE transactions SET
			type = $2, amount = $3, currency = $4, category_id = $5,
			note = $6, date = $7, updated_at = now()
		WHERE id = $1
		RETURNING id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
	`, tx.ID, tx.Type, tx.Amount, tx.Currency, tx.CategoryID,
		tx.Note, tx.Date,
	).Scan(
		&tx.ID, &tx.Type, &tx.Amount, &tx.Currency, &tx.AccountID,
		&tx.CounterAccountID, &tx.CategoryID, &tx.Date, &tx.Time,
		&tx.Note, pq.Array(&tx.Tags), &tx.ExchangeRate, &tx.CounterAmount,
		&tx.FeeAmount, &tx.FeeAccountID, &tx.PersonID, &tx.LinkedTransactionID,
		&tx.IsBuildingFund, &tx.RecurringRuleID, &tx.BalanceDelta, &tx.CreatedAt, &tx.UpdatedAt,
	)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("updating transaction: %w", err)
	}
	return tx, nil
}

// LinkTransactionsTx links two transactions to each other within a DB transaction.
func (r *TransactionRepo) LinkTransactionsTx(ctx context.Context, dbTx *sql.Tx, id1, id2 string) error {
	_, err := dbTx.ExecContext(ctx, `
		UPDATE transactions SET linked_transaction_id = $2 WHERE id = $1
	`, id1, id2)
	if err != nil {
		return fmt.Errorf("linking %s → %s: %w", id1, id2, err)
	}
	_, err = dbTx.ExecContext(ctx, `
		UPDATE transactions SET linked_transaction_id = $2 WHERE id = $1
	`, id2, id1)
	if err != nil {
		return fmt.Errorf("linking %s → %s: %w", id2, id1, err)
	}
	return nil
}

// Delete removes a transaction by ID.
func (r *TransactionRepo) Delete(ctx context.Context, id string) error {
	result, err := r.db.ExecContext(ctx, `DELETE FROM transactions WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("deleting transaction: %w", err)
	}
	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

// DeleteTx removes a transaction within an existing database transaction.
func (r *TransactionRepo) DeleteTx(ctx context.Context, dbTx *sql.Tx, id string) error {
	result, err := dbTx.ExecContext(ctx, `DELETE FROM transactions WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("deleting transaction: %w", err)
	}
	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

// BeginTx starts a database transaction.
// This lets the service layer group multiple operations atomically.
// Similar to DB::transaction() in Laravel or transaction.atomic() in Django.
func (r *TransactionRepo) BeginTx(ctx context.Context) (*sql.Tx, error) {
	return r.db.BeginTx(ctx, nil)
}

// UpdateBalanceTx updates an account balance within a database transaction.
func (r *TransactionRepo) UpdateBalanceTx(ctx context.Context, dbTx *sql.Tx, accountID string, delta float64) error {
	result, err := dbTx.ExecContext(ctx, `
		UPDATE accounts SET current_balance = current_balance + $2, updated_at = now()
		WHERE id = $1
	`, accountID, delta)
	if err != nil {
		return fmt.Errorf("updating balance: %w", err)
	}
	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

// TransactionFilter holds optional filter parameters for listing transactions.
// Like Laravel's query scopes or Django's Q objects — build up filters dynamically.
type TransactionFilter struct {
	AccountID  string
	CategoryID string
	Type       string // "expense", "income", etc.
	DateFrom   *time.Time
	DateTo     *time.Time
	Search     string // full-text search on note field
	Limit      int
	Offset     int
}

// GetFiltered retrieves transactions matching the given filters.
// Builds a dynamic WHERE clause based on which filters are set.
func (r *TransactionRepo) GetFiltered(ctx context.Context, f TransactionFilter) ([]models.Transaction, error) {
	query := `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE 1=1`

	var args []any
	argN := 1

	if f.AccountID != "" {
		query += fmt.Sprintf(" AND account_id = $%d", argN)
		args = append(args, f.AccountID)
		argN++
	}
	if f.CategoryID != "" {
		query += fmt.Sprintf(" AND category_id = $%d", argN)
		args = append(args, f.CategoryID)
		argN++
	}
	if f.Type != "" {
		query += fmt.Sprintf(" AND type = $%d", argN)
		args = append(args, f.Type)
		argN++
	}
	if f.DateFrom != nil {
		query += fmt.Sprintf(" AND date >= $%d", argN)
		args = append(args, *f.DateFrom)
		argN++
	}
	if f.DateTo != nil {
		query += fmt.Sprintf(" AND date <= $%d", argN)
		args = append(args, *f.DateTo)
		argN++
	}
	if f.Search != "" {
		query += fmt.Sprintf(" AND note ILIKE $%d", argN)
		args = append(args, "%"+f.Search+"%")
		argN++
	}

	query += " ORDER BY date DESC, created_at DESC"

	limit := f.Limit
	if limit <= 0 {
		limit = 50
	}
	query += fmt.Sprintf(" LIMIT $%d", argN)
	args = append(args, limit)
	argN++

	if f.Offset > 0 {
		query += fmt.Sprintf(" OFFSET $%d", argN)
		args = append(args, f.Offset)
	}

	return r.queryTransactions(ctx, query, args...)
}

// GetLastUsedAccountID returns the account_id from the most recent expense or income transaction.
// Returns empty string if no history exists.
func (r *TransactionRepo) GetLastUsedAccountID(ctx context.Context) (string, error) {
	var accountID string
	err := r.db.QueryRowContext(ctx, `
		SELECT account_id FROM transactions
		WHERE type IN ('expense', 'income')
		ORDER BY created_at DESC LIMIT 1
	`).Scan(&accountID)
	if err != nil {
		return "", err
	}
	return accountID, nil
}

// GetRecentCategoryIDs returns category IDs ordered by recent usage frequency.
// Looks at the last 50 expense/income transactions with a category set.
func (r *TransactionRepo) GetRecentCategoryIDs(ctx context.Context, txType string, limit int) ([]string, error) {
	if limit <= 0 {
		limit = 20
	}
	rows, err := r.db.QueryContext(ctx, `
		SELECT category_id FROM (
			SELECT category_id, MAX(created_at) as last_used, COUNT(*) as freq
			FROM transactions
			WHERE category_id IS NOT NULL AND type = $1
			GROUP BY category_id
		) sub
		ORDER BY freq DESC, last_used DESC
		LIMIT $2
	`, txType, limit)
	if err != nil {
		return nil, fmt.Errorf("querying recent categories: %w", err)
	}
	defer rows.Close()

	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

// GetConsecutiveCategoryID returns the category_id if it was used for the last N
// consecutive expense or income transactions. Returns empty string otherwise.
func (r *TransactionRepo) GetConsecutiveCategoryID(ctx context.Context, txType string, consecutiveCount int) (string, error) {
	if consecutiveCount <= 0 {
		consecutiveCount = 3
	}
	rows, err := r.db.QueryContext(ctx, `
		SELECT category_id FROM transactions
		WHERE type = $1 AND category_id IS NOT NULL
		ORDER BY created_at DESC LIMIT $2
	`, txType, consecutiveCount)
	if err != nil {
		return "", fmt.Errorf("querying consecutive categories: %w", err)
	}
	defer rows.Close()

	var firstID string
	count := 0
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return "", err
		}
		if count == 0 {
			firstID = id
		}
		if id != firstID {
			return "", nil // not all the same
		}
		count++
	}
	if count >= consecutiveCount {
		return firstID, nil
	}
	return "", nil
}

// GetBuildingFundBalance sums all building fund transactions.
// Income adds to the fund, expenses subtract from it.
func (r *TransactionRepo) GetBuildingFundBalance(ctx context.Context) (float64, error) {
	var balance float64
	err := r.db.QueryRowContext(ctx, `
		SELECT COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END), 0)
		FROM transactions WHERE is_building_fund = true
	`).Scan(&balance)
	if err != nil {
		return 0, fmt.Errorf("querying building fund balance: %w", err)
	}
	return balance, nil
}

// GetBuildingFundTransactions retrieves all transactions marked as building fund.
func (r *TransactionRepo) GetBuildingFundTransactions(ctx context.Context, limit int) ([]models.Transaction, error) {
	if limit <= 0 {
		limit = 100
	}
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id, category_id,
			date, time, note, tags, exchange_rate, counter_amount, fee_amount, fee_account_id,
			person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE is_building_fund = true
		ORDER BY date DESC, created_at DESC LIMIT $1
	`, limit)
}

// GetByDateRange retrieves all transactions within a date range (for CSV export).
func (r *TransactionRepo) GetByDateRange(ctx context.Context, from, to time.Time) ([]models.Transaction, error) {
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id, category_id,
			date, time, note, tags, exchange_rate, counter_amount, fee_amount, fee_account_id,
			person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE date >= $1 AND date <= $2
		ORDER BY date DESC, created_at DESC
	`, from, to)
}

func (r *TransactionRepo) queryTransactions(ctx context.Context, query string, args ...any) ([]models.Transaction, error) {
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("querying transactions: %w", err)
	}
	defer rows.Close()

	var transactions []models.Transaction
	for rows.Next() {
		var tx models.Transaction
		if err := rows.Scan(
			&tx.ID, &tx.Type, &tx.Amount, &tx.Currency, &tx.AccountID,
			&tx.CounterAccountID, &tx.CategoryID, &tx.Date, &tx.Time,
			&tx.Note, pq.Array(&tx.Tags), &tx.ExchangeRate, &tx.CounterAmount,
			&tx.FeeAmount, &tx.FeeAccountID, &tx.PersonID, &tx.LinkedTransactionID,
			&tx.IsBuildingFund, &tx.RecurringRuleID, &tx.BalanceDelta, &tx.CreatedAt, &tx.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("scanning transaction: %w", err)
		}
		transactions = append(transactions, tx)
	}
	return transactions, rows.Err()
}

// GetByPersonID returns all transactions linked to a specific person (loans, repayments).
// Used by the person detail page (TASK-070).
func (r *TransactionRepo) GetByPersonID(ctx context.Context, personID string, limit int) ([]models.Transaction, error) {
	if limit <= 0 {
		limit = 100
	}
	return r.queryTransactions(ctx, fmt.Sprintf(`
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE person_id = $1
		ORDER BY date DESC, created_at DESC LIMIT %d
	`, limit), personID)
}

// GetByAccountDateRange returns transactions for a specific account within a date range.
// Used by credit card statement view (TASK-071) to show transactions in a billing period.
func (r *TransactionRepo) GetByAccountDateRange(ctx context.Context, accountID string, from, to time.Time) ([]models.Transaction, error) {
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE account_id = $1 AND date >= $2 AND date <= $3
		ORDER BY date DESC, created_at DESC
	`, accountID, from, to)
}

// GetPaymentsToAccount returns income/transfer transactions that credit a specific account.
// Used by credit card payment history (TASK-075).
func (r *TransactionRepo) GetPaymentsToAccount(ctx context.Context, accountID string, limit int) ([]models.Transaction, error) {
	if limit <= 0 {
		limit = 20
	}
	return r.queryTransactions(ctx, fmt.Sprintf(`
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions
		WHERE (account_id = $1 OR counter_account_id = $1)
		  AND balance_delta > 0
		  AND type IN ('income', 'transfer')
		ORDER BY date DESC, created_at DESC
		LIMIT %d
	`, limit), accountID)
}

// HasDepositInRange checks if an account received a deposit >= minAmount within a date range.
// Used by account health checking (TASK-068) to verify minimum monthly deposit.
func (r *TransactionRepo) HasDepositInRange(ctx context.Context, accountID string, minAmount float64, from, to time.Time) bool {
	var exists bool
	_ = r.db.QueryRowContext(ctx, `
		SELECT EXISTS(
			SELECT 1 FROM transactions
			WHERE account_id = $1 AND type = 'income' AND amount >= $2
			  AND date >= $3 AND date < $4
		)
	`, accountID, minAmount, from, to).Scan(&exists)
	return exists
}
