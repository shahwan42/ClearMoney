package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/lib/pq"
)

// AccountRepo handles database operations for accounts.
// Accounts belong to institutions (like a hasMany relationship in Laravel/Eloquent).
type AccountRepo struct {
	db *sql.DB
}

func NewAccountRepo(db *sql.DB) *AccountRepo {
	return &AccountRepo{db: db}
}

// Create inserts a new account and sets current_balance = initial_balance.
func (r *AccountRepo) Create(ctx context.Context, acc models.Account) (models.Account, error) {
	acc.CurrentBalance = acc.InitialBalance

	// Default metadata to empty JSON object if nil
	if acc.Metadata == nil {
		acc.Metadata = json.RawMessage(`{}`)
	}

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
func (r *AccountRepo) GetByID(ctx context.Context, id string) (models.Account, error) {
	var acc models.Account
	err := r.db.QueryRowContext(ctx, `
		SELECT id, institution_id, name, type, currency, current_balance,
			initial_balance, credit_limit, is_dormant, role_tags,
			display_order, metadata, created_at, updated_at
		FROM accounts WHERE id = $1
	`, id).Scan(
		&acc.ID, &acc.InstitutionID, &acc.Name, &acc.Type, &acc.Currency,
		&acc.CurrentBalance, &acc.InitialBalance, &acc.CreditLimit,
		&acc.IsDormant, pq.Array(&acc.RoleTags), &acc.DisplayOrder,
		&acc.Metadata, &acc.CreatedAt, &acc.UpdatedAt,
	)
	if err != nil {
		return models.Account{}, fmt.Errorf("getting account: %w", err)
	}
	return acc, nil
}

// GetAll retrieves all accounts ordered by display_order.
func (r *AccountRepo) GetAll(ctx context.Context) ([]models.Account, error) {
	return r.queryAccounts(ctx, `
		SELECT id, institution_id, name, type, currency, current_balance,
			initial_balance, credit_limit, is_dormant, role_tags,
			display_order, metadata, created_at, updated_at
		FROM accounts ORDER BY display_order, name
	`)
}

// GetByInstitution retrieves all accounts for a given institution.
// Similar to $institution->accounts in Laravel Eloquent.
func (r *AccountRepo) GetByInstitution(ctx context.Context, institutionID string) ([]models.Account, error) {
	return r.queryAccounts(ctx, `
		SELECT id, institution_id, name, type, currency, current_balance,
			initial_balance, credit_limit, is_dormant, role_tags,
			display_order, metadata, created_at, updated_at
		FROM accounts WHERE institution_id = $1
		ORDER BY display_order, name
	`, institutionID)
}

// Update modifies an existing account's fields (not balance — that's done via transactions).
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

// UpdateBalance atomically updates the account's current_balance.
// This is called by the transaction service after creating/deleting transactions.
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

// queryAccounts is a DRY helper that executes a query and scans the results
// into a slice of Account models. Used by GetAll and GetByInstitution.
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
			&acc.Metadata, &acc.CreatedAt, &acc.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("scanning account: %w", err)
		}
		accounts = append(accounts, acc)
	}
	return accounts, rows.Err()
}
