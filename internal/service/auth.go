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

	"github.com/shahwan42/clearmoney/internal/logutil"
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
	if err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM user_config").Scan(&count); err != nil {
		return false
	}
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
	logutil.LogEvent(ctx, "auth.setup_completed")
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

// LoginResult holds the outcome of a login attempt, including lockout state.
// The handler uses this to decide what to render (success, error, or lockout countdown).
type LoginResult struct {
	Success        bool
	Locked         bool
	LockedUntil    time.Time
	FailedAttempts int
}

// lockoutDuration returns the lockout duration based on the number of consecutive
// failed attempts. First 3 attempts are free, then delays escalate progressively.
// This makes brute-forcing a 4-digit PIN infeasible while being forgiving of typos.
func lockoutDuration(attempts int) time.Duration {
	switch {
	case attempts <= 3:
		return 0
	case attempts == 4:
		return 30 * time.Second
	case attempts == 5:
		return 1 * time.Minute
	case attempts == 6:
		return 5 * time.Minute
	case attempts == 7:
		return 15 * time.Minute
	default:
		return 1 * time.Hour
	}
}

// formatLockoutDuration converts seconds to a human-readable duration string.
func formatLockoutDuration(seconds int) string {
	if seconds < 60 {
		if seconds == 1 {
			return "1 second"
		}
		return fmt.Sprintf("%d seconds", seconds)
	}
	m := seconds / 60
	s := seconds % 60
	if s == 0 {
		if m == 1 {
			return "1 minute"
		}
		return fmt.Sprintf("%d minutes", m)
	}
	return fmt.Sprintf("%d min %d sec", m, s)
}

// CheckAndVerifyPIN verifies a PIN with brute-force protection.
// It checks lockout state before attempting verification, increments the failure
// counter on wrong PINs, and resets it on success. Lockout state is persisted in
// the database so it survives app restarts.
//
// This is like Laravel's ThrottlesLogins trait or Django's django-axes package,
// but simpler since we only have one user.
func (s *AuthService) CheckAndVerifyPIN(ctx context.Context, pin string) LoginResult {
	var hash string
	var failedAttempts int
	var lockedUntil sql.NullTime

	err := s.db.QueryRowContext(ctx,
		"SELECT pin_hash, failed_attempts, locked_until FROM user_config LIMIT 1",
	).Scan(&hash, &failedAttempts, &lockedUntil)
	if err != nil {
		return LoginResult{}
	}

	// Check if currently locked out
	if lockedUntil.Valid && lockedUntil.Time.After(time.Now()) {
		logutil.LogEvent(ctx, "auth.login_blocked_lockout")
		return LoginResult{Locked: true, LockedUntil: lockedUntil.Time, FailedAttempts: failedAttempts}
	}

	// Verify PIN
	if bcrypt.CompareHashAndPassword([]byte(hash), []byte(pin)) != nil {
		// Wrong PIN — increment counter atomically and set lockout
		var newAttempts int
		err := s.db.QueryRowContext(ctx,
			`UPDATE user_config
			 SET failed_attempts = failed_attempts + 1,
			     locked_until = CASE
			         WHEN failed_attempts + 1 > 3 THEN $1::timestamptz
			         ELSE NULL
			     END
			 RETURNING failed_attempts`,
			time.Now().Add(lockoutDuration(failedAttempts+1)),
		).Scan(&newAttempts)
		if err != nil {
			return LoginResult{FailedAttempts: failedAttempts + 1}
		}
		logutil.LogEvent(ctx, "auth.login_failed")
		result := LoginResult{FailedAttempts: newAttempts}
		if d := lockoutDuration(newAttempts); d > 0 {
			result.Locked = true
			result.LockedUntil = time.Now().Add(d)
		}
		return result
	}

	// Correct PIN — reset counter
	_, _ = s.db.ExecContext(ctx,
		"UPDATE user_config SET failed_attempts = 0, locked_until = NULL",
	)
	logutil.LogEvent(ctx, "auth.login_success")
	return LoginResult{Success: true}
}

// GetLockoutStatus returns the current lockout state without attempting verification.
// Used by the GET /login handler to show the countdown on page load.
func (s *AuthService) GetLockoutStatus(ctx context.Context) (locked bool, lockedUntil time.Time, err error) {
	var failedAttempts int
	var lt sql.NullTime
	err = s.db.QueryRowContext(ctx,
		"SELECT failed_attempts, locked_until FROM user_config LIMIT 1",
	).Scan(&failedAttempts, &lt)
	if err != nil {
		return false, time.Time{}, fmt.Errorf("getting lockout status: %w", err)
	}
	if lt.Valid && lt.Time.After(time.Now()) {
		return true, lt.Time, nil
	}
	return false, time.Time{}, nil
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
// Uses CheckAndVerifyPIN so that brute-force protection applies here too —
// an attacker with an active session can't bypass lockout via the settings page.
func (s *AuthService) ChangePin(ctx context.Context, currentPin, newPin string) error {
	result := s.CheckAndVerifyPIN(ctx, currentPin)
	if result.Locked {
		remaining := int(time.Until(result.LockedUntil).Seconds())
		if remaining < 1 {
			remaining = 1
		}
		return fmt.Errorf("too many failed attempts. Try again in %s", formatLockoutDuration(remaining))
	}
	if !result.Success {
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
	logutil.LogEvent(ctx, "auth.pin_changed")
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
