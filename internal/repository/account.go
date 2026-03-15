package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"

	"github.com/shahwan42/clearmoney/internal/models"
	// pq is the PostgreSQL driver helper library.
	// pq.Array() converts between Go slices and PostgreSQL array columns (text[], int[], etc.).
	// This is like Laravel's array casting: protected $casts = ['role_tags' => 'array'];
	// Or Django's ArrayField from django.contrib.postgres.fields.
	// See: https://pkg.go.dev/github.com/lib/pq#Array
	"github.com/lib/pq"
)

// AccountRepo handles database operations for accounts.
// Accounts belong to institutions (like a hasMany relationship in Laravel/Eloquent).
//
// Think of this as a dedicated Eloquent repository or Django Manager for the Account model.
// Unlike Eloquent where you call Account::find($id), here you call repo.GetByID(ctx, id).
//
// *sql.DB is Go's built-in connection pool — similar to the DB facade in Laravel
// or django.db.connection. It manages multiple connections automatically and is
// safe to use from multiple goroutines (like PHP-FPM workers or Django threads).
type AccountRepo struct {
	db *sql.DB
}

// NewAccountRepo creates a new repo instance. In Laravel, the service container
// auto-injects dependencies; in Go, we pass them explicitly (manual DI).
func NewAccountRepo(db *sql.DB) *AccountRepo {
	return &AccountRepo{db: db}
}

// Create inserts a new account and sets current_balance = initial_balance.
//
// context.Context (ctx) flows through every DB call — it carries deadlines and
// cancellation signals. Think of it like Laravel's request lifecycle: if the HTTP
// request is cancelled (user closes browser), ctx gets cancelled and the DB query
// is aborted. Every function that does I/O should accept and pass ctx along.
//
// Go returns errors as values instead of throwing exceptions. The (Account, error)
// return is like: [$account, $error] = $repo->create($data) — you always check
// the error. There's no try/catch in Go.
func (r *AccountRepo) Create(ctx context.Context, acc models.Account) (models.Account, error) {
	acc.CurrentBalance = acc.InitialBalance

	// Default metadata to empty JSON object if nil.
	// json.RawMessage stores raw JSON bytes — like Laravel's $casts['metadata' => 'array'].
	if acc.Metadata == nil {
		acc.Metadata = json.RawMessage(`{}`)
	}

	// QueryRowContext executes a query that returns a single row.
	// $1, $2, ... are PostgreSQL placeholders (Laravel uses ?, Django uses %s).
	// They prevent SQL injection — equivalent to prepared statements.
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO accounts (institution_id, name, type, currency, current_balance,
			initial_balance, credit_limit, is_dormant, role_tags, display_order, metadata)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		RETURNING id, created_at, updated_at
	`, acc.InstitutionID, acc.Name, acc.Type, acc.Currency,
		acc.CurrentBalance, acc.InitialBalance, acc.CreditLimit,
		acc.IsDormant, pq.Array(acc.RoleTags), acc.DisplayOrder, acc.Metadata,
	).Scan(&acc.ID, &acc.CreatedAt, &acc.UpdatedAt)

	if err != nil {
		return models.Account{}, fmt.Errorf("inserting account: %w", err)
	}
	return acc, nil
}

// GetByID retrieves a single account by UUID.
//
// Note the Scan call includes pq.Array(&acc.RoleTags) — this converts the
// PostgreSQL text[] array column into a Go []string slice. Without pq.Array(),
// the driver wouldn't know how to deserialize the array.
//
// &acc.Metadata and &acc.HealthConfig scan directly into json.RawMessage
// fields, which hold raw JSON bytes. PostgreSQL's JSONB type maps cleanly
// to json.RawMessage in Go.
//   Laravel:  protected $casts = ['metadata' => 'array', 'health_config' => 'array'];
//   Django:   metadata = JSONField(default=dict)
//   Go:       json.RawMessage (raw bytes, decoded when needed)
func (r *AccountRepo) GetByID(ctx context.Context, id string) (models.Account, error) {
	var acc models.Account
	err := r.db.QueryRowContext(ctx, `
		SELECT id, institution_id, name, type, currency, current_balance,
			initial_balance, credit_limit, is_dormant, role_tags,
			display_order, metadata, COALESCE(health_config, '{}'::jsonb), created_at, updated_at
		FROM accounts WHERE id = $1
	`, id).Scan(
		&acc.ID, &acc.InstitutionID, &acc.Name, &acc.Type, &acc.Currency,
		&acc.CurrentBalance, &acc.InitialBalance, &acc.CreditLimit,
		&acc.IsDormant, pq.Array(&acc.RoleTags), &acc.DisplayOrder,
		&acc.Metadata, &acc.HealthConfig, &acc.CreatedAt, &acc.UpdatedAt,
	)
	if err != nil {
		return models.Account{}, fmt.Errorf("getting account: %w", err)
	}
	return acc, nil
}

// GetAll retrieves all accounts ordered by display_order.
//   Laravel:  Account::orderBy('display_order')->orderBy('name')->get()
//   Django:   Account.objects.order_by('display_order', 'name')
func (r *AccountRepo) GetAll(ctx context.Context) ([]models.Account, error) {
	return r.queryAccounts(ctx, `
		SELECT id, institution_id, name, type, currency, current_balance,
			initial_balance, credit_limit, is_dormant, role_tags,
			display_order, metadata, COALESCE(health_config, '{}'::jsonb), created_at, updated_at
		FROM accounts ORDER BY display_order, name
	`)
}

// GetByInstitution retrieves all accounts for a given institution.
// Similar to $institution->accounts in Laravel Eloquent.
func (r *AccountRepo) GetByInstitution(ctx context.Context, institutionID string) ([]models.Account, error) {
	return r.queryAccounts(ctx, `
		SELECT id, institution_id, name, type, currency, current_balance,
			initial_balance, credit_limit, is_dormant, role_tags,
			display_order, metadata, COALESCE(health_config, '{}'::jsonb), created_at, updated_at
		FROM accounts WHERE institution_id = $1
		ORDER BY display_order, name
	`, institutionID)
}

// Update modifies an existing account's fields (not balance — that's done via transactions).
//
// Important: current_balance is NOT updated here. Balance changes flow through
// UpdateBalance() or UpdateBalanceTx() which use atomic SQL (current_balance + $delta).
// This prevents race conditions when concurrent requests modify the balance.
//   Laravel analogy: DB::table('accounts')->where('id', $id)->increment('current_balance', $delta)
func (r *AccountRepo) Update(ctx context.Context, acc models.Account) (models.Account, error) {
	err := r.db.QueryRowContext(ctx, `
		UPDATE accounts
		SET name = $2, type = $3, currency = $4, credit_limit = $5,
			is_dormant = $6, role_tags = $7, display_order = $8,
			metadata = $9, updated_at = now()
		WHERE id = $1
		RETURNING updated_at
	`, acc.ID, acc.Name, acc.Type, acc.Currency, acc.CreditLimit,
		acc.IsDormant, pq.Array(acc.RoleTags), acc.DisplayOrder, acc.Metadata,
	).Scan(&acc.UpdatedAt)

	if err != nil {
		return models.Account{}, fmt.Errorf("updating account: %w", err)
	}
	return acc, nil
}

// UpdateHealthConfig sets the health constraints for an account (TASK-068).
// The config is stored as JSONB in PostgreSQL — json.RawMessage passes raw JSON
// bytes directly to the driver without Go-side encoding/decoding.
//
//   Example JSON: {"min_balance": 5000, "min_monthly_deposit": 1000}
//   PostgreSQL:   health_config JSONB DEFAULT '{}'
//   Go:           json.RawMessage (alias for []byte)
func (r *AccountRepo) UpdateHealthConfig(ctx context.Context, id string, config json.RawMessage) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE accounts SET health_config = $2, updated_at = now() WHERE id = $1
	`, id, config)
	return err
}

// UpdateBalance atomically updates the account's current_balance using SQL arithmetic.
// This is called by the transaction service after creating/deleting transactions.
//
// The SQL `current_balance = current_balance + $2` is atomic at the DB level —
// even if two requests run simultaneously, PostgreSQL serializes the updates.
// This is safer than "read balance, add in Go, write back" which has a race condition.
//
//   Laravel:  DB::table('accounts')->where('id', $id)->increment('current_balance', $delta)
//   Django:   Account.objects.filter(id=id).update(current_balance=F('current_balance') + delta)
func (r *AccountRepo) UpdateBalance(ctx context.Context, id string, delta float64) error {
	result, err := r.db.ExecContext(ctx, `
		UPDATE accounts SET current_balance = current_balance + $2, updated_at = now()
		WHERE id = $1
	`, id, delta)
	if err != nil {
		return fmt.Errorf("updating balance: %w", err)
	}
	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

// Delete removes an account by ID.
func (r *AccountRepo) Delete(ctx context.Context, id string) error {
	result, err := r.db.ExecContext(ctx, `DELETE FROM accounts WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("deleting account: %w", err)
	}
	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

// ToggleDormant flips the is_dormant flag for an account.
// The SQL `NOT is_dormant` does the toggle at the DB level in one query —
// no need to read the current value first.
//
//   Laravel:  DB::statement('UPDATE accounts SET is_dormant = NOT is_dormant WHERE id = ?', [$id])
//   Django:   Account.objects.filter(id=id).update(is_dormant=~F('is_dormant'))  // bitwise NOT
func (r *AccountRepo) ToggleDormant(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE accounts SET is_dormant = NOT is_dormant, updated_at = now()
		WHERE id = $1
	`, id)
	return err
}

// UpdateDisplayOrder sets the display_order for an account.
func (r *AccountRepo) UpdateDisplayOrder(ctx context.Context, id string, order int) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE accounts SET display_order = $2, updated_at = now() WHERE id = $1
	`, id, order)
	return err
}

// queryAccounts is a DRY helper that executes a query and scans the results
// into a slice of Account models. Used by GetAll and GetByInstitution.
//
// The ...any parameter (variadic) accepts zero or more arguments of any type.
// This lets us reuse the same scan logic for different WHERE clauses.
//   - GetAll passes no args (no WHERE clause)
//   - GetByInstitution passes the institution ID
//
// In Laravel, you'd use query scopes for this. In Django, you'd chain QuerySet methods.
// In Go, we use a helper function with variadic args — simpler but equally DRY.
func (r *AccountRepo) queryAccounts(ctx context.Context, query string, args ...any) ([]models.Account, error) {
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("querying accounts: %w", err)
	}
	defer rows.Close()

	var accounts []models.Account
	for rows.Next() {
		var acc models.Account
		if err := rows.Scan(
			&acc.ID, &acc.InstitutionID, &acc.Name, &acc.Type, &acc.Currency,
			&acc.CurrentBalance, &acc.InitialBalance, &acc.CreditLimit,
			&acc.IsDormant, pq.Array(&acc.RoleTags), &acc.DisplayOrder,
			&acc.Metadata, &acc.HealthConfig, &acc.CreatedAt, &acc.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("scanning account: %w", err)
		}
		accounts = append(accounts, acc)
	}
	return accounts, rows.Err()
}
