// Package repository — transaction.go is the largest repository, handling all
// transaction-related database operations including CRUD, filtering, DB transactions,
// balance updates, category suggestions, and deposit checking.
//
// This file demonstrates several important Go/PostgreSQL patterns:
//   - *sql.Tx (database transactions) for atomicity
//   - Dynamic query building with parameterized placeholders
//   - ILIKE for case-insensitive search (PostgreSQL-specific)
//   - COALESCE for handling NULL aggregates
//   - Subqueries and window functions
//
// See: https://pkg.go.dev/database/sql#Tx
package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	// pq.Array() handles PostgreSQL array columns (text[]) — converts Go []string
	// slices to/from the PostgreSQL wire format for arrays.
	"github.com/lib/pq"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/timeutil"
)

// TransactionRepo handles database operations for the transactions table.
// This is the most feature-rich repository — it has the most methods because
// transactions are the core of a finance tracker.
//
//   Laravel:  Transaction model + TransactionRepository with scopes
//   Django:   Transaction.objects with custom Manager methods
type TransactionRepo struct {
	db *sql.DB
}

// NewTransactionRepo creates a new TransactionRepo.
func NewTransactionRepo(db *sql.DB) *TransactionRepo {
	return &TransactionRepo{db: db}
}

// Create inserts a new transaction record.
//
// IMPORTANT: This does NOT update account balances — that's the service layer's
// job inside a database transaction (see service.TransactionService.Create).
// The repository is "dumb" — it only inserts/reads data, no business logic.
//
// The query uses 19 positional parameters ($1..$19). PostgreSQL requires numbered
// placeholders unlike MySQL's `?`. The order must match the args list exactly.
func (r *TransactionRepo) Create(ctx context.Context, userID string, tx models.Transaction) (models.Transaction, error) {
	tx.UserID = userID
	if tx.Date.IsZero() {
		tx.Date = timeutil.Now()
	}

	err := r.db.QueryRowContext(ctx, `
		INSERT INTO transactions (user_id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
		RETURNING id, created_at, updated_at
	`, userID, tx.Type, tx.Amount, tx.Currency, tx.AccountID, tx.CounterAccountID,
		tx.CategoryID, tx.Date, tx.Time, tx.Note, pq.Array(tx.Tags),
		tx.ExchangeRate, tx.CounterAmount, tx.FeeAmount, tx.FeeAccountID,
		tx.PersonID, tx.LinkedTransactionID, tx.RecurringRuleID,
		tx.BalanceDelta,
	).Scan(&tx.ID, &tx.CreatedAt, &tx.UpdatedAt)

	if err != nil {
		return models.Transaction{}, fmt.Errorf("inserting transaction: %w", err)
	}
	return tx, nil
}

// CreateTx inserts a transaction within an existing database transaction (*sql.Tx).
//
// *sql.Tx is Go's database transaction object — all queries run on it share the
// same transaction and are committed or rolled back together.
//
//   Laravel:  DB::transaction(function () { ... });  // closure-based
//   Django:   with transaction.atomic(): ...          // context manager
//   Go:       dbTx, _ := db.BeginTx(ctx, nil)        // explicit begin/commit/rollback
//
// The "Tx" suffix convention: Create() uses db directly, CreateTx() uses a *sql.Tx.
// This lets the service layer group multiple operations atomically:
//   1. BeginTx → get *sql.Tx
//   2. CreateTx (insert transaction record)
//   3. UpdateBalanceTx (adjust account balance)
//   4. Commit or Rollback
//
// See: https://pkg.go.dev/database/sql#Tx
func (r *TransactionRepo) CreateTx(ctx context.Context, userID string, dbTx *sql.Tx, tx models.Transaction) (models.Transaction, error) {
	tx.UserID = userID
	if tx.Date.IsZero() {
		tx.Date = timeutil.Now()
	}

	err := dbTx.QueryRowContext(ctx, `
		INSERT INTO transactions (user_id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
		RETURNING id, created_at, updated_at
	`, userID, tx.Type, tx.Amount, tx.Currency, tx.AccountID, tx.CounterAccountID,
		tx.CategoryID, tx.Date, tx.Time, tx.Note, pq.Array(tx.Tags),
		tx.ExchangeRate, tx.CounterAmount, tx.FeeAmount, tx.FeeAccountID,
		tx.PersonID, tx.LinkedTransactionID, tx.RecurringRuleID,
		tx.BalanceDelta,
	).Scan(&tx.ID, &tx.CreatedAt, &tx.UpdatedAt)

	if err != nil {
		return models.Transaction{}, fmt.Errorf("inserting transaction: %w", err)
	}
	return tx, nil
}

// GetByID retrieves a single transaction by its UUID.
//
// Note the many nullable columns scanned here (CounterAccountID, CategoryID, Note, etc.).
// In Go, nullable DB columns map to pointer types (*string, *float64) or sql.Null* types.
// If the column is NULL, the pointer will be nil after Scan.
//   Laravel:  nullable columns are simply null in PHP (dynamic typing)
//   Django:   nullable fields are None
//   Go:       use *string for nullable strings, *float64 for nullable floats
func (r *TransactionRepo) GetByID(ctx context.Context, userID string, id string) (models.Transaction, error) {
	var tx models.Transaction
	err := r.db.QueryRowContext(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE id = $1 AND user_id = $2
	`, id, userID).Scan(
		&tx.ID, &tx.Type, &tx.Amount, &tx.Currency, &tx.AccountID,
		&tx.CounterAccountID, &tx.CategoryID, &tx.Date, &tx.Time,
		&tx.Note, pq.Array(&tx.Tags), &tx.ExchangeRate, &tx.CounterAmount,
		&tx.FeeAmount, &tx.FeeAccountID, &tx.PersonID, &tx.LinkedTransactionID,
		&tx.RecurringRuleID, &tx.BalanceDelta, &tx.CreatedAt, &tx.UpdatedAt,
	)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("getting transaction: %w", err)
	}
	return tx, nil
}

// GetRecent retrieves the most recent transactions across all accounts.
func (r *TransactionRepo) GetRecent(ctx context.Context, userID string, limit int) ([]models.Transaction, error) {
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE user_id = $1 ORDER BY date DESC, created_at DESC LIMIT $2
	`, userID, limit)
}

// GetByAccount retrieves transactions for a specific account.
func (r *TransactionRepo) GetByAccount(ctx context.Context, userID string, accountID string, limit int) ([]models.Transaction, error) {
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE account_id = $1 AND user_id = $2
		ORDER BY date DESC, created_at DESC LIMIT $3
	`, accountID, userID, limit)
}

// Update modifies a transaction's editable fields (type, amount, currency, category, note, date).
//
// Uses RETURNING to get the full updated row back — this avoids a separate SELECT
// and ensures we return the most current data.
//   Laravel:  $tx->update([...]); $tx->fresh();  // two queries
//   Go:       UPDATE ... RETURNING *               // one query, PostgreSQL-specific
func (r *TransactionRepo) Update(ctx context.Context, userID string, tx models.Transaction) (models.Transaction, error) {
	err := r.db.QueryRowContext(ctx, `
		UPDATE transactions SET
			type = $2, amount = $3, currency = $4, category_id = $5,
			note = $6, date = $7, updated_at = now()
		WHERE id = $1 AND user_id = $8
		RETURNING id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
	`, tx.ID, tx.Type, tx.Amount, tx.Currency, tx.CategoryID,
		tx.Note, tx.Date, userID,
	).Scan(
		&tx.ID, &tx.Type, &tx.Amount, &tx.Currency, &tx.AccountID,
		&tx.CounterAccountID, &tx.CategoryID, &tx.Date, &tx.Time,
		&tx.Note, pq.Array(&tx.Tags), &tx.ExchangeRate, &tx.CounterAmount,
		&tx.FeeAmount, &tx.FeeAccountID, &tx.PersonID, &tx.LinkedTransactionID,
		&tx.RecurringRuleID, &tx.BalanceDelta, &tx.CreatedAt, &tx.UpdatedAt,
	)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("updating transaction: %w", err)
	}
	return tx, nil
}

// UpdateTx modifies a transaction within an existing database transaction (*sql.Tx).
// Same as Update() but uses the passed-in *sql.Tx instead of the connection pool.
// This ensures the update is part of an atomic operation with balance adjustments.
func (r *TransactionRepo) UpdateTx(ctx context.Context, userID string, dbTx *sql.Tx, tx models.Transaction) (models.Transaction, error) {
	err := dbTx.QueryRowContext(ctx, `
		UPDATE transactions SET
			type = $2, amount = $3, currency = $4, category_id = $5,
			note = $6, date = $7, updated_at = now()
		WHERE id = $1 AND user_id = $8
		RETURNING id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
	`, tx.ID, tx.Type, tx.Amount, tx.Currency, tx.CategoryID,
		tx.Note, tx.Date, userID,
	).Scan(
		&tx.ID, &tx.Type, &tx.Amount, &tx.Currency, &tx.AccountID,
		&tx.CounterAccountID, &tx.CategoryID, &tx.Date, &tx.Time,
		&tx.Note, pq.Array(&tx.Tags), &tx.ExchangeRate, &tx.CounterAmount,
		&tx.FeeAmount, &tx.FeeAccountID, &tx.PersonID, &tx.LinkedTransactionID,
		&tx.RecurringRuleID, &tx.BalanceDelta, &tx.CreatedAt, &tx.UpdatedAt,
	)
	if err != nil {
		return models.Transaction{}, fmt.Errorf("updating transaction: %w", err)
	}
	return tx, nil
}

// LinkTransactionsTx links two transactions to each other within a DB transaction.
// Used for transfers: the "from" and "to" transaction records point at each other
// via linked_transaction_id, creating a bidirectional link. Two UPDATE statements
// are needed because each row references the other.
func (r *TransactionRepo) LinkTransactionsTx(ctx context.Context, userID string, dbTx *sql.Tx, id1, id2 string) error {
	_, err := dbTx.ExecContext(ctx, `
		UPDATE transactions SET linked_transaction_id = $2 WHERE id = $1 AND user_id = $3
	`, id1, id2, userID)
	if err != nil {
		return fmt.Errorf("linking %s → %s: %w", id1, id2, err)
	}
	_, err = dbTx.ExecContext(ctx, `
		UPDATE transactions SET linked_transaction_id = $2 WHERE id = $1 AND user_id = $3
	`, id2, id1, userID)
	if err != nil {
		return fmt.Errorf("linking %s → %s: %w", id2, id1, err)
	}
	return nil
}

// Delete removes a transaction by ID.
func (r *TransactionRepo) Delete(ctx context.Context, userID string, id string) error {
	result, err := r.db.ExecContext(ctx, `DELETE FROM transactions WHERE id = $1 AND user_id = $2`, id, userID)
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
func (r *TransactionRepo) DeleteTx(ctx context.Context, userID string, dbTx *sql.Tx, id string) error {
	result, err := dbTx.ExecContext(ctx, `DELETE FROM transactions WHERE id = $1 AND user_id = $2`, id, userID)
	if err != nil {
		return fmt.Errorf("deleting transaction: %w", err)
	}
	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

// BeginTx starts a database transaction and returns a *sql.Tx handle.
// The service layer uses this to group multiple operations atomically.
//
//   Laravel:  DB::beginTransaction(); ... DB::commit(); // or DB::rollBack()
//   Django:   with transaction.atomic(): ...
//   Go:       dbTx, err := repo.BeginTx(ctx)
//             defer dbTx.Rollback()  // no-op if already committed
//             ... do work on dbTx ...
//             dbTx.Commit()
//
// The nil second argument uses default transaction options (READ COMMITTED isolation).
// See: https://pkg.go.dev/database/sql#DB.BeginTx
func (r *TransactionRepo) BeginTx(ctx context.Context) (*sql.Tx, error) {
	return r.db.BeginTx(ctx, nil)
}

// UpdateBalanceTx updates an account balance within a database transaction.
func (r *TransactionRepo) UpdateBalanceTx(ctx context.Context, userID string, dbTx *sql.Tx, accountID string, delta float64) error {
	result, err := dbTx.ExecContext(ctx, `
		UPDATE accounts SET current_balance = current_balance + $2, updated_at = now()
		WHERE id = $1 AND user_id = $3
	`, accountID, delta, userID)
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
//
// This struct acts like a "filter bag" — the caller sets whichever fields are
// relevant, and GetFiltered() builds a dynamic WHERE clause from them.
//
//   Laravel analogy:  Query scopes: Transaction::forAccount($id)->ofType('expense')->search('grocery')
//   Django analogy:   Q objects: Transaction.objects.filter(Q(account_id=id) & Q(type='expense'))
//
// Using a struct instead of many function parameters is a Go idiom called the
// "options struct" pattern. It's cleaner than 8+ function parameters.
type TransactionFilter struct {
	AccountID  string
	CategoryID string
	Type       string // "expense", "income", etc.
	DateFrom   *time.Time
	DateTo     *time.Time
	Search     string // text search on note field using ILIKE
	Limit      int
	Offset     int
}

// GetFiltered retrieves transactions matching the given filters.
// Builds a dynamic WHERE clause based on which filters are set.
//
// This demonstrates dynamic query building in Go — the Go equivalent of
// Laravel's query builder chaining or Django's ORM filter chaining:
//
//   Laravel:  $query = Transaction::query();
//             if ($accountId) $query->where('account_id', $accountId);
//             if ($search) $query->where('note', 'ILIKE', "%$search%");
//
// In Go without an ORM, we concatenate SQL strings with numbered placeholders.
// The `WHERE 1=1` trick lets us always append `AND ...` conditions without
// worrying whether it's the first condition or not.
//
// argN tracks the next placeholder number ($1, $2, ...) as we add filters.
// This is necessary because PostgreSQL uses numbered (not positional) placeholders.
//
// ILIKE is PostgreSQL's case-insensitive LIKE (MySQL uses LIKE with a
// case-insensitive collation by default; PostgreSQL's LIKE is case-sensitive).
func (r *TransactionRepo) GetFiltered(ctx context.Context, userID string, f TransactionFilter) ([]models.Transaction, error) {
	query := `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE user_id = $1`

	var args []any
	args = append(args, userID)
	argN := 2

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
func (r *TransactionRepo) GetLastUsedAccountID(ctx context.Context, userID string) (string, error) {
	var accountID string
	err := r.db.QueryRowContext(ctx, `
		SELECT account_id FROM transactions
		WHERE type IN ('expense', 'income') AND user_id = $1
		ORDER BY created_at DESC LIMIT 1
	`, userID).Scan(&accountID)
	if err != nil {
		return "", err
	}
	return accountID, nil
}

// GetRecentCategoryIDs returns category IDs ordered by recent usage frequency.
// Uses a subquery to group by category, count frequency, and sort by most-used.
//
// The SQL pattern: subquery groups + aggregates, outer query sorts.
//   SELECT category_id FROM (
//     SELECT category_id, MAX(created_at) as last_used, COUNT(*) as freq
//     FROM transactions WHERE ...
//     GROUP BY category_id
//   ) sub ORDER BY freq DESC, last_used DESC
//
// This is used by the "smart category suggest" feature (TASK-079) to pre-select
// the most likely category when creating a new transaction.
func (r *TransactionRepo) GetRecentCategoryIDs(ctx context.Context, userID string, txType string, limit int) ([]string, error) {
	if limit <= 0 {
		limit = 20
	}
	rows, err := r.db.QueryContext(ctx, `
		SELECT category_id FROM (
			SELECT category_id, MAX(created_at) as last_used, COUNT(*) as freq
			FROM transactions
			WHERE category_id IS NOT NULL AND type = $1 AND user_id = $2
			GROUP BY category_id
		) sub
		ORDER BY freq DESC, last_used DESC
		LIMIT $3
	`, txType, userID, limit)
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
func (r *TransactionRepo) GetConsecutiveCategoryID(ctx context.Context, userID string, txType string, consecutiveCount int) (string, error) {
	if consecutiveCount <= 0 {
		consecutiveCount = 3
	}
	rows, err := r.db.QueryContext(ctx, `
		SELECT category_id FROM transactions
		WHERE type = $1 AND category_id IS NOT NULL AND user_id = $2
		ORDER BY created_at DESC LIMIT $3
	`, txType, userID, consecutiveCount)
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

// GetByDateRange retrieves all transactions within a date range (for CSV export).
func (r *TransactionRepo) GetByDateRange(ctx context.Context, userID string, from, to time.Time) ([]models.Transaction, error) {
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id, category_id,
			date, time, note, tags, exchange_rate, counter_amount, fee_amount, fee_account_id,
			person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE date >= $1 AND date <= $2 AND user_id = $3
		ORDER BY date DESC, created_at DESC
	`, from, to, userID)
}

// queryTransactions is the shared DRY helper for scanning transaction rows.
// Every method that returns []models.Transaction delegates here.
// The ...any variadic parameter accepts the query's placeholder values.
//
// Pattern: QueryContext → defer Close → for Next { Scan } → check Err
// This is the canonical Go pattern for reading multiple rows.
// See: https://pkg.go.dev/database/sql#Rows
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
			&tx.RecurringRuleID, &tx.BalanceDelta, &tx.CreatedAt, &tx.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("scanning transaction: %w", err)
		}
		transactions = append(transactions, tx)
	}
	return transactions, rows.Err()
}

// GetByPersonID returns all transactions linked to a specific person (loans, repayments).
// Used by the person detail page (TASK-070).
func (r *TransactionRepo) GetByPersonID(ctx context.Context, userID string, personID string, limit int) ([]models.Transaction, error) {
	if limit <= 0 {
		limit = 100
	}
	return r.queryTransactions(ctx, fmt.Sprintf(`
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE person_id = $1 AND user_id = $2
		ORDER BY date DESC, created_at DESC LIMIT %d
	`, limit), personID, userID)
}

// GetByAccountDateRange returns transactions for a specific account within a date range.
// Used by credit card statement view (TASK-071) to show transactions in a billing period.
func (r *TransactionRepo) GetByAccountDateRange(ctx context.Context, userID string, accountID string, from, to time.Time) ([]models.Transaction, error) {
	return r.queryTransactions(ctx, `
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions WHERE account_id = $1 AND date >= $2 AND date <= $3 AND user_id = $4
		ORDER BY date DESC, created_at DESC
	`, accountID, from, to, userID)
}

// GetPaymentsToAccount returns income/transfer transactions that credit a specific account.
// Used by credit card payment history (TASK-075).
func (r *TransactionRepo) GetPaymentsToAccount(ctx context.Context, userID string, accountID string, limit int) ([]models.Transaction, error) {
	if limit <= 0 {
		limit = 20
	}
	return r.queryTransactions(ctx, fmt.Sprintf(`
		SELECT id, type, amount, currency, account_id, counter_account_id,
			category_id, date, time, note, tags, exchange_rate, counter_amount,
			fee_amount, fee_account_id, person_id, linked_transaction_id,
			recurring_rule_id, balance_delta, created_at, updated_at
		FROM transactions
		WHERE (account_id = $1 OR counter_account_id = $1)
		  AND balance_delta > 0
		  AND type IN ('income', 'transfer')
		  AND user_id = $2
		ORDER BY date DESC, created_at DESC
		LIMIT %d
	`, limit), accountID, userID)
}

// SuggestCategory returns the most common category ID for transactions whose note matches a keyword.
// Uses ILIKE for case-insensitive pattern matching (TASK-079).
//
// The SQL uses GROUP BY + ORDER BY COUNT(*) DESC to find the most frequently
// used category for similar notes. LIMIT 1 returns only the top match.
//
// ILIKE '%' || $1 || '%' is PostgreSQL's case-insensitive LIKE with string
// concatenation (||). The % wildcards match any text before/after the keyword.
//   Laravel:  where('note', 'ILIKE', "%{$keyword}%")
//   Django:   filter(note__icontains=keyword)
//
// Returns empty string on error or no match (silently fails — acceptable for suggestions).
func (r *TransactionRepo) SuggestCategory(ctx context.Context, userID string, noteKeyword string) string {
	if noteKeyword == "" {
		return ""
	}
	var categoryID string
	err := r.db.QueryRowContext(ctx, `
		SELECT category_id FROM transactions
		WHERE note ILIKE '%' || $1 || '%' AND category_id IS NOT NULL AND user_id = $2
		GROUP BY category_id
		ORDER BY COUNT(*) DESC
		LIMIT 1
	`, noteKeyword, userID).Scan(&categoryID)
	if err != nil {
		return ""
	}
	return categoryID
}

// HasDepositInRange checks if an account received a deposit >= minAmount within a date range.
// Used by account health checking (TASK-068) to verify minimum monthly deposit rules.
//
// SELECT EXISTS(...) is an efficient way to check for existence without fetching data.
// PostgreSQL stops scanning as soon as it finds one matching row.
//   Laravel:  Transaction::where(...)->exists()
//   Django:   Transaction.objects.filter(...).exists()
//
// The `_ = ...Scan(&exists)` discards any error — on failure, exists defaults to false.
// This is acceptable here because a failed check should not block the UI.
func (r *TransactionRepo) HasDepositInRange(ctx context.Context, userID string, accountID string, minAmount float64, from, to time.Time) bool {
	var exists bool
	_ = r.db.QueryRowContext(ctx, `
		SELECT EXISTS(
			SELECT 1 FROM transactions
			WHERE account_id = $1 AND type = 'income' AND amount >= $2
			  AND date >= $3 AND date < $4 AND user_id = $5
		)
	`, accountID, minAmount, from, to, userID).Scan(&exists)
	return exists
}

// TransactionDisplayRow extends Transaction with display fields from JOINed data.
// Used by templates that need account name and running balance alongside the
// base transaction data. The running balance is computed via a SQL window function
// over all transactions for the account (not just the filtered set).
type TransactionDisplayRow struct {
	models.Transaction
	AccountName    string  // from accounts.name
	RunningBalance float64 // balance after this transaction was applied
}

// GetByIDEnriched retrieves a single transaction with account name and running balance.
func (r *TransactionRepo) GetByIDEnriched(ctx context.Context, userID string, id string) (TransactionDisplayRow, error) {
	rows, err := r.queryTransactionsEnriched(ctx, `
		SELECT sub.id, sub.type, sub.amount, sub.currency, sub.account_id,
			sub.counter_account_id, sub.category_id, sub.date, sub.time, sub.note,
			sub.tags, sub.exchange_rate, sub.counter_amount, sub.fee_amount,
			sub.fee_account_id, sub.person_id, sub.linked_transaction_id,
			sub.recurring_rule_id, sub.balance_delta, sub.created_at, sub.updated_at,
			sub.account_name, sub.running_balance
		FROM (
			SELECT t.id, t.type, t.amount, t.currency, t.account_id,
				t.counter_account_id, t.category_id, t.date, t.time, t.note,
				t.tags, t.exchange_rate, t.counter_amount, t.fee_amount,
				t.fee_account_id, t.person_id, t.linked_transaction_id,
				t.recurring_rule_id, t.balance_delta, t.created_at, t.updated_at,
				a.name AS account_name,
				a.current_balance - COALESCE(
					SUM(t.balance_delta) OVER (
						PARTITION BY t.account_id
						ORDER BY t.date DESC, t.created_at DESC
						ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
					), 0
				) AS running_balance
			FROM transactions t
			JOIN accounts a ON a.id = t.account_id
			WHERE t.user_id = $1
		) sub
		WHERE sub.id = $2
	`, userID, id)
	if err != nil {
		return TransactionDisplayRow{}, fmt.Errorf("getting enriched transaction: %w", err)
	}
	if len(rows) == 0 {
		return TransactionDisplayRow{}, fmt.Errorf("getting enriched transaction: %w", sql.ErrNoRows)
	}
	return rows[0], nil
}

// GetRecentEnriched retrieves recent transactions with account name and running balance.
func (r *TransactionRepo) GetRecentEnriched(ctx context.Context, userID string, limit int) ([]TransactionDisplayRow, error) {
	return r.queryTransactionsEnriched(ctx, fmt.Sprintf(`
		SELECT sub.id, sub.type, sub.amount, sub.currency, sub.account_id,
			sub.counter_account_id, sub.category_id, sub.date, sub.time, sub.note,
			sub.tags, sub.exchange_rate, sub.counter_amount, sub.fee_amount,
			sub.fee_account_id, sub.person_id, sub.linked_transaction_id,
			sub.recurring_rule_id, sub.balance_delta, sub.created_at, sub.updated_at,
			sub.account_name, sub.running_balance
		FROM (
			SELECT t.id, t.type, t.amount, t.currency, t.account_id,
				t.counter_account_id, t.category_id, t.date, t.time, t.note,
				t.tags, t.exchange_rate, t.counter_amount, t.fee_amount,
				t.fee_account_id, t.person_id, t.linked_transaction_id,
				t.recurring_rule_id, t.balance_delta, t.created_at, t.updated_at,
				a.name AS account_name,
				a.current_balance - COALESCE(
					SUM(t.balance_delta) OVER (
						PARTITION BY t.account_id
						ORDER BY t.date DESC, t.created_at DESC
						ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
					), 0
				) AS running_balance
			FROM transactions t
			JOIN accounts a ON a.id = t.account_id
			WHERE t.user_id = $1
		) sub
		ORDER BY sub.date DESC, sub.created_at DESC
		LIMIT %d
	`, limit), userID)
}

// GetFilteredEnriched retrieves filtered transactions with account name and running balance.
// The running balance is computed over ALL transactions for each account (via the inner
// subquery), then filters are applied on the outer query. This ensures the balance shown
// is always the true account balance at that point in time, regardless of active filters.
func (r *TransactionRepo) GetFilteredEnriched(ctx context.Context, userID string, f TransactionFilter) ([]TransactionDisplayRow, error) {
	query := `
		SELECT sub.id, sub.type, sub.amount, sub.currency, sub.account_id,
			sub.counter_account_id, sub.category_id, sub.date, sub.time, sub.note,
			sub.tags, sub.exchange_rate, sub.counter_amount, sub.fee_amount,
			sub.fee_account_id, sub.person_id, sub.linked_transaction_id,
			sub.recurring_rule_id, sub.balance_delta, sub.created_at, sub.updated_at,
			sub.account_name, sub.running_balance
		FROM (
			SELECT t.id, t.type, t.amount, t.currency, t.account_id,
				t.counter_account_id, t.category_id, t.date, t.time, t.note,
				t.tags, t.exchange_rate, t.counter_amount, t.fee_amount,
				t.fee_account_id, t.person_id, t.linked_transaction_id,
				t.recurring_rule_id, t.balance_delta, t.created_at, t.updated_at,
				a.name AS account_name,
				a.current_balance - COALESCE(
					SUM(t.balance_delta) OVER (
						PARTITION BY t.account_id
						ORDER BY t.date DESC, t.created_at DESC
						ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
					), 0
				) AS running_balance
			FROM transactions t
			JOIN accounts a ON a.id = t.account_id
			WHERE t.user_id = $1
		) sub
		WHERE 1=1`

	var args []any
	args = append(args, userID)
	argN := 2

	if f.AccountID != "" {
		query += fmt.Sprintf(" AND sub.account_id = $%d", argN)
		args = append(args, f.AccountID)
		argN++
	}
	if f.CategoryID != "" {
		query += fmt.Sprintf(" AND sub.category_id = $%d", argN)
		args = append(args, f.CategoryID)
		argN++
	}
	if f.Type != "" {
		query += fmt.Sprintf(" AND sub.type = $%d", argN)
		args = append(args, f.Type)
		argN++
	}
	if f.DateFrom != nil {
		query += fmt.Sprintf(" AND sub.date >= $%d", argN)
		args = append(args, *f.DateFrom)
		argN++
	}
	if f.DateTo != nil {
		query += fmt.Sprintf(" AND sub.date <= $%d", argN)
		args = append(args, *f.DateTo)
		argN++
	}
	if f.Search != "" {
		query += fmt.Sprintf(" AND sub.note ILIKE $%d", argN)
		args = append(args, "%"+f.Search+"%")
		argN++
	}

	query += " ORDER BY sub.date DESC, sub.created_at DESC"

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

	return r.queryTransactionsEnriched(ctx, query, args...)
}

// queryTransactionsEnriched scans transaction rows with account_name and running_balance.
// Parallel to queryTransactions but handles 22 columns instead of 20.
func (r *TransactionRepo) queryTransactionsEnriched(ctx context.Context, query string, args ...any) ([]TransactionDisplayRow, error) {
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("querying enriched transactions: %w", err)
	}
	defer rows.Close()

	var results []TransactionDisplayRow
	for rows.Next() {
		var row TransactionDisplayRow
		if err := rows.Scan(
			&row.ID, &row.Type, &row.Amount, &row.Currency, &row.AccountID,
			&row.CounterAccountID, &row.CategoryID, &row.Date, &row.Time,
			&row.Note, pq.Array(&row.Tags), &row.ExchangeRate, &row.CounterAmount,
			&row.FeeAmount, &row.FeeAccountID, &row.PersonID, &row.LinkedTransactionID,
			&row.RecurringRuleID, &row.BalanceDelta, &row.CreatedAt, &row.UpdatedAt,
			&row.AccountName, &row.RunningBalance,
		); err != nil {
			return nil, fmt.Errorf("scanning enriched transaction: %w", err)
		}
		results = append(results, row)
	}
	return results, rows.Err()
}
