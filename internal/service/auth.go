// auth.go — AuthService handles PIN-based authentication for ClearMoney.
//
// This is a SINGLE-USER app — there's one PIN, one session key, no users table.
// The auth flow is:
//   1. First visit: setup page asks for a 4-6 digit PIN
//   2. PIN is hashed with bcrypt and stored in user_config table
//   3. A random session key is generated for signing HMAC session cookies
//   4. On login: user enters PIN, service verifies against bcrypt hash
//   5. On success: a signed cookie is set (valid for 30 days)
//
// Laravel analogy: Like a stripped-down Auth system. Laravel uses bcrypt by default
// (Hash::make($pin)) and stores it in the users table. Here, we use the same bcrypt
// but with a simpler user_config table (just pin_hash + session_key, no email/name).
// The session cookie is like Laravel's session guard but signed with HMAC instead of
// using session IDs stored in a database/file.
//
// Django analogy: Like a simplified django.contrib.auth with make_password/check_password
// for bcrypt hashing, and a signed cookie using Django's signing framework.
//
// Security packages used:
//   - golang.org/x/crypto/bcrypt: same bcrypt algorithm as PHP's password_hash().
//     See: https://pkg.go.dev/golang.org/x/crypto/bcrypt
//   - crypto/rand: cryptographically secure random number generator for session keys.
//     Like PHP's random_bytes() or Python's secrets module.
//     See: https://pkg.go.dev/crypto/rand
//   - encoding/hex: converts random bytes to hex string (for session key storage).
//     See: https://pkg.go.dev/encoding/hex
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
// Uses *sql.DB directly (no repository) because auth operations are simple
// and tightly coupled to the schema (user_config table with just 2 columns).
type AuthService struct {
	db *sql.DB
}

func NewAuthService(db *sql.DB) *AuthService {
	return &AuthService{db: db}
}

// IsSetup checks if a PIN has been configured.
// Returns true if a user_config row exists. On first run, this returns false,
// and the app redirects to the setup page. Like checking if Laravel's .env has been
// configured or if Django's initial migration has run.
func (s *AuthService) IsSetup(ctx context.Context) bool {
	var count int
	s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM user_config").Scan(&count)
	return count > 0
}

// Setup creates the initial PIN and session key (first-time setup only).
// PIN is hashed with bcrypt (same algorithm as PHP's password_hash() which Laravel uses).
// bcrypt.DefaultCost is 10 — the same as Laravel's default rounds.
//
// The session key is a random 32-byte hex string used for HMAC-signing cookies.
// This is like Laravel's APP_KEY — it signs cookies so they can't be tampered with.
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

	// Delete any existing config — single-user app, only one row should exist.
	if _, err := s.db.ExecContext(ctx, `DELETE FROM user_config`); err != nil {
		return fmt.Errorf("clearing existing config: %w", err)
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
// bcrypt.CompareHashAndPassword is constant-time (prevents timing attacks).
// Returns bool (not error) — a simplified API since the caller only needs yes/no.
// Like Laravel's Hash::check($pin, $hash) or Django's check_password().
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
// Go constants are typed and immutable (like PHP's const or Python's convention).
// See: https://go.dev/tour/basics/15
const SessionCookieName = "clearmoney_session"

// SessionMaxAge is how long the session cookie lasts (30 days).
// time.Duration is Go's way of representing time spans. The expression
// 30 * 24 * time.Hour reads naturally as "30 days worth of hours."
const SessionMaxAge = 30 * 24 * time.Hour

// generateSessionKey creates a random 32-byte hex string for signing cookies.
// crypto/rand.Read fills a byte slice with cryptographically secure random data.
// This is unexported (lowercase) — only callable within this package.
func generateSessionKey() (string, error) {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}
