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
			is_building_fund, recurring_rule_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
		RETURNING id, created_at, updated_at
	`, tx.Type, tx.Amount, tx.Currency, tx.AccountID, tx.CounterAccountID,
		tx.CategoryID, tx.Date, tx.Time, tx.Note, pq.Array(tx.Tags),
		tx.ExchangeRate, tx.CounterAmount, tx.FeeAmount, tx.FeeAccountID,
		tx.PersonID, tx.LinkedTransactionID, tx.IsBuildingFund, tx.RecurringRuleID,
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
			is_building_fund, recurring_rule_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
		RETURNING id, created_at, updated_at
	`, tx.Type, tx.Amount, tx.Currency, tx.AccountID, tx.CounterAccountID,
		tx.CategoryID, tx.Date, tx.Time, tx.Note, pq.Array(tx.Tags),
		tx.ExchangeRate, tx.CounterAmount, tx.FeeAmount, tx.FeeAccountID,
		tx.PersonID, tx.LinkedTransactionID, tx.IsBuildingFund, tx.RecurringRuleID,
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
			is_building_fund, recurring_rule_id, created_at, updated_at
		FROM transactions WHERE id = $1
	`, id).Scan(
		&tx.ID, &tx.Type, &tx.Amount, &tx.Currency, &tx.AccountID,
		&tx.CounterAccountID, &tx.CategoryID, &tx.Date, &tx.Time,
		&tx.Note, pq.Array(&tx.Tags), &tx.ExchangeRate, &tx.CounterAmount,
		&tx.FeeAmount, &tx.FeeAccountID, &tx.PersonID, &tx.LinkedTransactionID,
		&tx.IsBuildingFund, &tx.RecurringRuleID, &tx.CreatedAt, &tx.UpdatedAt,
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
			is_building_fund, recurring_rule_id, created_at, updated_at
		FROM transactions ORDER BY date DESC, created_at DESC LIMIT $1
	`, limit)
}

// GetByAccount retrieves transactions for a specific account.
func (r *TransactionRepo) GetByAccount(ctx context.Context, accountID string, limit int) ([]models.Transaction, error) {
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			is_building_fund, recurring_rule_id, created_at, updated_at
		FROM transactions WHERE account_id = $1
		ORDER BY date DESC, created_at DESC LIMIT $2
	`, accountID, limit)
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
			&tx.IsBuildingFund, &tx.RecurringRuleID, &tx.CreatedAt, &tx.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("scanning transaction: %w", err)
		}
		transactions = append(transactions, tx)
	}
	return transactions, rows.Err()
}
