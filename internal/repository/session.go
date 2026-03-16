// session.go — Repository for the sessions table.
//
// Server-side sessions replace the old HMAC-signed cookies. Each session is a
// DB row mapping a random token to a user_id with an expiry. The auth middleware
// looks up the session by token on every request.
//
// Laravel analogy: Like the sessions table with SESSION_DRIVER=database.
// Django analogy: Like django_session — server-side session storage.
package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
)

// SessionRepo handles all database operations for the sessions table.
type SessionRepo struct {
	db *sql.DB
}

func NewSessionRepo(db *sql.DB) *SessionRepo {
	return &SessionRepo{db: db}
}

// Create inserts a new session and returns it.
func (r *SessionRepo) Create(ctx context.Context, userID, token string, expiresAt time.Time) (models.Session, error) {
	var session models.Session
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO sessions (user_id, token, expires_at)
		VALUES ($1, $2, $3)
		RETURNING id, user_id, token, expires_at, created_at
	`, userID, token, expiresAt).Scan(
		&session.ID, &session.UserID, &session.Token,
		&session.ExpiresAt, &session.CreatedAt,
	)
	if err != nil {
		return models.Session{}, fmt.Errorf("creating session: %w", err)
	}
	return session, nil
}

// GetByToken retrieves a session by its token (used by auth middleware on every request).
// Returns sql.ErrNoRows if not found.
func (r *SessionRepo) GetByToken(ctx context.Context, token string) (models.Session, error) {
	var session models.Session
	err := r.db.QueryRowContext(ctx, `
		SELECT id, user_id, token, expires_at, created_at
		FROM sessions WHERE token = $1
	`, token).Scan(
		&session.ID, &session.UserID, &session.Token,
		&session.ExpiresAt, &session.CreatedAt,
	)
	if err != nil {
		return models.Session{}, fmt.Errorf("getting session by token: %w", err)
	}
	return session, nil
}

// DeleteByToken removes a session (logout).
func (r *SessionRepo) DeleteByToken(ctx context.Context, token string) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM sessions WHERE token = $1`, token)
	if err != nil {
		return fmt.Errorf("deleting session: %w", err)
	}
	return nil
}

// DeleteByUserID removes all sessions for a user (force logout everywhere).
func (r *SessionRepo) DeleteByUserID(ctx context.Context, userID string) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM sessions WHERE user_id = $1`, userID)
	if err != nil {
		return fmt.Errorf("deleting user sessions: %w", err)
	}
	return nil
}

// DeleteExpired removes all expired sessions (cleanup job).
func (r *SessionRepo) DeleteExpired(ctx context.Context) (int64, error) {
	result, err := r.db.ExecContext(ctx, `DELETE FROM sessions WHERE expires_at < NOW()`)
	if err != nil {
		return 0, fmt.Errorf("deleting expired sessions: %w", err)
	}
	count, _ := result.RowsAffected()
	return count, nil
}
