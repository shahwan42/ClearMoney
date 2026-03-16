// auth_token.go — Repository for the auth_tokens table (magic link tokens).
//
// Auth tokens are short-lived (15 min), single-use tokens sent via email.
// Rate limiting queries (CountRecentByEmail, CountToday) live here because
// they're simple counts on the same table — no business logic involved.
//
// Laravel analogy: Like a TokenRepository for password_resets but for magic links.
// Django analogy: Like querying a PasswordResetToken model with filter/count.
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/shahwan42/clearmoney/internal/models"
)

// AuthTokenRepo handles all database operations for the auth_tokens table.
type AuthTokenRepo struct {
	db *sql.DB
}

func NewAuthTokenRepo(db *sql.DB) *AuthTokenRepo {
	return &AuthTokenRepo{db: db}
}

// Create inserts a new auth token and returns it.
func (r *AuthTokenRepo) Create(ctx context.Context, email, token, purpose string, ttlMinutes int) (models.AuthToken, error) {
	var at models.AuthToken
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO auth_tokens (email, token, purpose, expires_at)
		VALUES (LOWER($1), $2, $3, NOW() + ($4 || ' minutes')::INTERVAL)
		RETURNING id, email, token, purpose, expires_at, used, created_at
	`, email, token, purpose, fmt.Sprintf("%d", ttlMinutes)).Scan(
		&at.ID, &at.Email, &at.Token, &at.Purpose,
		&at.ExpiresAt, &at.Used, &at.CreatedAt,
	)
	if err != nil {
		return models.AuthToken{}, fmt.Errorf("creating auth token: %w", err)
	}
	return at, nil
}

// GetByToken retrieves an auth token by its token string.
func (r *AuthTokenRepo) GetByToken(ctx context.Context, token string) (models.AuthToken, error) {
	var at models.AuthToken
	err := r.db.QueryRowContext(ctx, `
		SELECT id, email, token, purpose, expires_at, used, created_at
		FROM auth_tokens WHERE token = $1
	`, token).Scan(
		&at.ID, &at.Email, &at.Token, &at.Purpose,
		&at.ExpiresAt, &at.Used, &at.CreatedAt,
	)
	if err != nil {
		return models.AuthToken{}, fmt.Errorf("getting auth token: %w", err)
	}
	return at, nil
}

// MarkUsed sets the token as used (single-use enforcement).
func (r *AuthTokenRepo) MarkUsed(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `UPDATE auth_tokens SET used = TRUE WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("marking token used: %w", err)
	}
	return nil
}

// CountRecentByEmail counts tokens created for this email in the last N minutes.
// Used for per-email cooldown (e.g., 1 per 5 minutes).
func (r *AuthTokenRepo) CountRecentByEmail(ctx context.Context, email string, minutes int) (int, error) {
	var count int
	err := r.db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM auth_tokens
		WHERE LOWER(email) = LOWER($1)
		  AND created_at > NOW() - ($2 || ' minutes')::INTERVAL
	`, email, fmt.Sprintf("%d", minutes)).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("counting recent tokens by email: %w", err)
	}
	return count, nil
}

// CountTodayByEmail counts tokens created for this email in the last 24 hours.
// Used for per-email daily limit (e.g., 3 per day).
func (r *AuthTokenRepo) CountTodayByEmail(ctx context.Context, email string) (int, error) {
	var count int
	err := r.db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM auth_tokens
		WHERE LOWER(email) = LOWER($1)
		  AND created_at > NOW() - INTERVAL '24 hours'
	`, email).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("counting daily tokens by email: %w", err)
	}
	return count, nil
}

// CountToday counts all tokens created in the last 24 hours (global daily cap).
func (r *AuthTokenRepo) CountToday(ctx context.Context) (int, error) {
	var count int
	err := r.db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM auth_tokens
		WHERE created_at > NOW() - INTERVAL '24 hours'
	`).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("counting daily tokens: %w", err)
	}
	return count, nil
}

// HasUnexpiredToken checks if an unexpired, unused token exists for this email and purpose.
// Used for token reuse — if one exists, we don't send a new email.
func (r *AuthTokenRepo) HasUnexpiredToken(ctx context.Context, email, purpose string) (bool, error) {
	var exists bool
	err := r.db.QueryRowContext(ctx, `
		SELECT EXISTS(
			SELECT 1 FROM auth_tokens
			WHERE LOWER(email) = LOWER($1)
			  AND purpose = $2
			  AND used = FALSE
			  AND expires_at > NOW()
		)
	`, email, purpose).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("checking unexpired token: %w", err)
	}
	return exists, nil
}

// GetUnexpiredToken returns the token string for an existing unexpired, unused token.
// Returns sql.ErrNoRows if none found. Used in dev mode to log the magic link URL
// when token reuse kicks in.
func (r *AuthTokenRepo) GetUnexpiredToken(ctx context.Context, email, purpose string) (string, error) {
	var token string
	err := r.db.QueryRowContext(ctx, `
		SELECT token FROM auth_tokens
		WHERE LOWER(email) = LOWER($1)
		  AND purpose = $2
		  AND used = FALSE
		  AND expires_at > NOW()
		LIMIT 1
	`, email, purpose).Scan(&token)
	if err != nil {
		return "", fmt.Errorf("getting unexpired token: %w", err)
	}
	return token, nil
}

// DeleteExpired removes all expired tokens (cleanup job).
func (r *AuthTokenRepo) DeleteExpired(ctx context.Context) (int64, error) {
	result, err := r.db.ExecContext(ctx, `DELETE FROM auth_tokens WHERE expires_at < NOW()`)
	if err != nil {
		return 0, fmt.Errorf("deleting expired tokens: %w", err)
	}
	count, _ := result.RowsAffected()
	return count, nil
}
