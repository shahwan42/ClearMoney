package service

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"fmt"
	"time"

	"golang.org/x/crypto/bcrypt"
)

// AuthService handles PIN-based authentication.
// This is a single-user app — only one PIN and session key exist.
// Think of it like Laravel's Auth facade but much simpler (no users table, no roles).
type AuthService struct {
	db *sql.DB
}

func NewAuthService(db *sql.DB) *AuthService {
	return &AuthService{db: db}
}

// IsSetup checks if a PIN has been configured.
// Returns true if a user_config row exists.
func (s *AuthService) IsSetup(ctx context.Context) bool {
	var count int
	s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM user_config").Scan(&count)
	return count > 0
}

// Setup creates the initial PIN and session key.
// PIN is hashed with bcrypt (same algorithm Laravel uses by default).
func (s *AuthService) Setup(ctx context.Context, pin string) error {
	if len(pin) < 4 || len(pin) > 6 {
		return fmt.Errorf("PIN must be 4-6 digits")
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(pin), bcrypt.DefaultCost)
	if err != nil {
		return fmt.Errorf("hashing PIN: %w", err)
	}

	sessionKey, err := generateSessionKey()
	if err != nil {
		return fmt.Errorf("generating session key: %w", err)
	}

	_, err = s.db.ExecContext(ctx, `
		INSERT INTO user_config (pin_hash, session_key) VALUES ($1, $2)
	`, string(hash), sessionKey)
	if err != nil {
		return fmt.Errorf("saving config: %w", err)
	}
	return nil
}

// VerifyPIN checks if the given PIN matches the stored hash.
func (s *AuthService) VerifyPIN(ctx context.Context, pin string) bool {
	var hash string
	err := s.db.QueryRowContext(ctx, "SELECT pin_hash FROM user_config LIMIT 1").Scan(&hash)
	if err != nil {
		return false
	}
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(pin)) == nil
}

// GetSessionKey retrieves the session signing key.
func (s *AuthService) GetSessionKey(ctx context.Context) (string, error) {
	var key string
	err := s.db.QueryRowContext(ctx, "SELECT session_key FROM user_config LIMIT 1").Scan(&key)
	if err != nil {
		return "", fmt.Errorf("getting session key: %w", err)
	}
	return key, nil
}

// ChangePin verifies the current PIN and updates to a new one.
func (s *AuthService) ChangePin(ctx context.Context, currentPin, newPin string) error {
	if !s.VerifyPIN(ctx, currentPin) {
		return fmt.Errorf("current PIN is incorrect")
	}
	if len(newPin) < 4 || len(newPin) > 6 {
		return fmt.Errorf("new PIN must be 4-6 digits")
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(newPin), bcrypt.DefaultCost)
	if err != nil {
		return fmt.Errorf("hashing PIN: %w", err)
	}

	_, err = s.db.ExecContext(ctx, `UPDATE user_config SET pin_hash = $1`, string(hash))
	if err != nil {
		return fmt.Errorf("updating PIN: %w", err)
	}
	return nil
}

// SessionCookieName is the name of the auth session cookie.
const SessionCookieName = "clearmoney_session"

// SessionMaxAge is how long the session cookie lasts (30 days).
const SessionMaxAge = 30 * 24 * time.Hour

// generateSessionKey creates a random 32-byte hex string for signing cookies.
func generateSessionKey() (string, error) {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}
