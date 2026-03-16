// user.go — Repository for the users table.
//
// Handles CRUD for user accounts. Users are created during magic link verification
// (registration flow) or already exist (login flow). Email lookups are
// case-insensitive via LOWER() to match the database unique index.
//
// Laravel analogy: Like User::where('email', $email)->first() or User::create([...]).
// Django analogy: Like User.objects.get(email__iexact=email) or User.objects.create_user(...).
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/shahwan42/clearmoney/internal/models"
)

// UserRepo handles all database operations for the users table.
type UserRepo struct {
	db *sql.DB
}

func NewUserRepo(db *sql.DB) *UserRepo {
	return &UserRepo{db: db}
}

// Create inserts a new user and returns it with generated fields.
func (r *UserRepo) Create(ctx context.Context, email string) (models.User, error) {
	var user models.User
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO users (email) VALUES (LOWER($1))
		RETURNING id, email, created_at, updated_at
	`, email).Scan(&user.ID, &user.Email, &user.CreatedAt, &user.UpdatedAt)
	if err != nil {
		return models.User{}, fmt.Errorf("creating user: %w", err)
	}
	return user, nil
}

// GetByID retrieves a user by UUID.
func (r *UserRepo) GetByID(ctx context.Context, id string) (models.User, error) {
	var user models.User
	err := r.db.QueryRowContext(ctx, `
		SELECT id, email, created_at, updated_at FROM users WHERE id = $1
	`, id).Scan(&user.ID, &user.Email, &user.CreatedAt, &user.UpdatedAt)
	if err != nil {
		return models.User{}, fmt.Errorf("getting user by id: %w", err)
	}
	return user, nil
}

// GetAllIDs returns the IDs of all users. Used by background jobs to iterate per-user.
func (r *UserRepo) GetAllIDs(ctx context.Context) ([]string, error) {
	rows, err := r.db.QueryContext(ctx, `SELECT id FROM users ORDER BY created_at`)
	if err != nil {
		return nil, fmt.Errorf("listing user ids: %w", err)
	}
	defer rows.Close()
	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, fmt.Errorf("scanning user id: %w", err)
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

// GetByEmail retrieves a user by email (case-insensitive).
func (r *UserRepo) GetByEmail(ctx context.Context, email string) (models.User, error) {
	var user models.User
	err := r.db.QueryRowContext(ctx, `
		SELECT id, email, created_at, updated_at FROM users WHERE LOWER(email) = LOWER($1)
	`, email).Scan(&user.ID, &user.Email, &user.CreatedAt, &user.UpdatedAt)
	if err != nil {
		return models.User{}, fmt.Errorf("getting user by email: %w", err)
	}
	return user, nil
}
