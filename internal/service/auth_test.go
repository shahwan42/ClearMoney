// auth_test.go — Integration tests for brute-force login prevention.
//
// Tests the progressive lockout system that protects PIN-based auth:
//   - First 3 failed attempts: no lockout (forgiveness for typos)
//   - 4th failure: 30s lockout
//   - 5th: 1m, 6th: 5m, 7th: 15m, 8+: 1h
//   - Successful login resets the counter
//   - Lockout blocks even correct PINs
//   - ChangePin shares the same lockout counter
//
// These are integration tests that run against a real PostgreSQL database.
// Like Laravel's RefreshDatabase trait, each test starts with a clean user_config.
package service

import (
	"context"
	"testing"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
	"golang.org/x/crypto/bcrypt"
)

// setupAuthForTest creates a user_config row with PIN "1234" and zeroed lockout state.
func setupAuthForTest(t *testing.T) *AuthService {
	t.Helper()
	db := testutil.NewTestDB(t)
	ctx := context.Background()

	db.ExecContext(ctx, "TRUNCATE TABLE user_config")

	hash, err := bcrypt.GenerateFromPassword([]byte("1234"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("hashing pin: %v", err)
	}
	_, err = db.ExecContext(ctx, `INSERT INTO user_config (pin_hash, session_key) VALUES ($1, $2)`,
		string(hash), "test-session-key")
	if err != nil {
		t.Fatalf("inserting user_config: %v", err)
	}
	return NewAuthService(db)
}

func TestLockoutDuration(t *testing.T) {
	tests := []struct {
		attempts int
		expected time.Duration
	}{
		{0, 0},
		{1, 0},
		{2, 0},
		{3, 0},
		{4, 30 * time.Second},
		{5, 1 * time.Minute},
		{6, 5 * time.Minute},
		{7, 15 * time.Minute},
		{8, 1 * time.Hour},
		{9, 1 * time.Hour},
		{100, 1 * time.Hour},
	}
	for _, tt := range tests {
		got := lockoutDuration(tt.attempts)
		if got != tt.expected {
			t.Errorf("lockoutDuration(%d) = %v, want %v", tt.attempts, got, tt.expected)
		}
	}
}

func TestCheckAndVerifyPIN_SuccessOnFirstAttempt(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	result := svc.CheckAndVerifyPIN(ctx, "1234")
	if !result.Success {
		t.Error("expected success with correct PIN")
	}
	if result.Locked {
		t.Error("should not be locked")
	}
}

func TestCheckAndVerifyPIN_FailureIncrementsCounter(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	result := svc.CheckAndVerifyPIN(ctx, "9999")
	if result.Success {
		t.Error("expected failure with wrong PIN")
	}
	if result.FailedAttempts != 1 {
		t.Errorf("expected 1 failed attempt, got %d", result.FailedAttempts)
	}
	if result.Locked {
		t.Error("should not be locked after 1 failure")
	}
}

func TestCheckAndVerifyPIN_ThreeFreeAttempts(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	// First 3 failures should not trigger lockout
	for i := 1; i <= 3; i++ {
		result := svc.CheckAndVerifyPIN(ctx, "9999")
		if result.Locked {
			t.Errorf("should not be locked after %d failures", i)
		}
		if result.FailedAttempts != i {
			t.Errorf("expected %d failed attempts, got %d", i, result.FailedAttempts)
		}
	}
}

func TestCheckAndVerifyPIN_LockoutAt4(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	// Exhaust 3 free attempts
	for i := 0; i < 3; i++ {
		svc.CheckAndVerifyPIN(ctx, "9999")
	}

	// 4th failure should trigger 30s lockout
	result := svc.CheckAndVerifyPIN(ctx, "9999")
	if !result.Locked {
		t.Error("expected lockout after 4th failure")
	}
	if result.FailedAttempts != 4 {
		t.Errorf("expected 4 failed attempts, got %d", result.FailedAttempts)
	}
}

func TestCheckAndVerifyPIN_LockoutBlocksCorrectPIN(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	// Trigger lockout
	for i := 0; i < 4; i++ {
		svc.CheckAndVerifyPIN(ctx, "9999")
	}

	// Even correct PIN should be blocked while locked
	result := svc.CheckAndVerifyPIN(ctx, "1234")
	if result.Success {
		t.Error("expected correct PIN to be blocked during lockout")
	}
	if !result.Locked {
		t.Error("expected locked state")
	}
}

func TestCheckAndVerifyPIN_SuccessResetsCounter(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	// 2 failures, then success
	svc.CheckAndVerifyPIN(ctx, "9999")
	svc.CheckAndVerifyPIN(ctx, "9999")
	result := svc.CheckAndVerifyPIN(ctx, "1234")
	if !result.Success {
		t.Error("expected success")
	}

	// After reset, 3 more failures should not lock (counter was reset to 0)
	for i := 0; i < 3; i++ {
		r := svc.CheckAndVerifyPIN(ctx, "9999")
		if r.Locked {
			t.Errorf("should not be locked after reset + %d failures", i+1)
		}
	}
}

func TestCheckAndVerifyPIN_ProgressiveEscalation(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	// We can't easily test the exact lockout duration from the result (it uses time.Now()),
	// but we can verify the lockout flag is set for attempts 4+.
	for i := 1; i <= 8; i++ {
		result := svc.CheckAndVerifyPIN(ctx, "9999")
		if i <= 3 && result.Locked {
			t.Errorf("should not be locked at attempt %d", i)
		}
		if i == 4 && !result.Locked {
			t.Error("should be locked at attempt 4")
		}
		// For attempts 5+, we need to expire the lockout first by manipulating DB
		if i >= 4 && result.Locked {
			// Expire the lockout so we can continue testing
			svc.db.ExecContext(ctx, "UPDATE user_config SET locked_until = NOW() - INTERVAL '1 second'")
		}
	}
}

func TestCheckAndVerifyPIN_LockoutExpires(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	// Trigger lockout
	for i := 0; i < 4; i++ {
		svc.CheckAndVerifyPIN(ctx, "9999")
	}

	// Manually expire the lockout (simulate time passing)
	svc.db.ExecContext(ctx, "UPDATE user_config SET locked_until = NOW() - INTERVAL '1 second'")

	// Correct PIN should now work
	result := svc.CheckAndVerifyPIN(ctx, "1234")
	if !result.Success {
		t.Error("expected success after lockout expired")
	}
}

func TestGetLockoutStatus_NotLockedByDefault(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	locked, _, err := svc.GetLockoutStatus(ctx)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if locked {
		t.Error("should not be locked by default")
	}
}

func TestGetLockoutStatus_LockedAfterFailures(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	for i := 0; i < 4; i++ {
		svc.CheckAndVerifyPIN(ctx, "9999")
	}

	locked, lockedUntil, err := svc.GetLockoutStatus(ctx)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !locked {
		t.Error("should be locked after 4 failures")
	}
	if lockedUntil.Before(time.Now()) {
		t.Error("locked_until should be in the future")
	}
}

func TestChangePin_LockoutApplies(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	// Trigger lockout via wrong PINs
	for i := 0; i < 4; i++ {
		svc.CheckAndVerifyPIN(ctx, "9999")
	}

	// ChangePin should be blocked during lockout
	err := svc.ChangePin(ctx, "1234", "5678")
	if err == nil {
		t.Error("expected error during lockout")
	}
	if err != nil && !contains(err.Error(), "too many failed attempts") {
		t.Errorf("expected lockout error, got: %v", err)
	}
}

func TestChangePin_WrongCurrentPINIncrementsCounter(t *testing.T) {
	svc := setupAuthForTest(t)
	ctx := context.Background()

	// 3 wrong ChangePin attempts
	for i := 0; i < 3; i++ {
		svc.ChangePin(ctx, "9999", "5678")
	}

	// 4th should trigger lockout
	err := svc.ChangePin(ctx, "9999", "5678")
	if err == nil {
		t.Error("expected error")
	}
	if err != nil && !contains(err.Error(), "too many failed attempts") {
		t.Errorf("expected lockout error on 4th attempt, got: %v", err)
	}
}

func TestFormatLockoutDuration(t *testing.T) {
	tests := []struct {
		seconds  int
		expected string
	}{
		{1, "1 second"},
		{5, "5 seconds"},
		{30, "30 seconds"},
		{59, "59 seconds"},
		{60, "1 minute"},
		{120, "2 minutes"},
		{300, "5 minutes"},
		{90, "1 min 30 sec"},
		{3600, "60 minutes"},
		{3661, "61 min 1 sec"},
	}
	for _, tt := range tests {
		got := formatLockoutDuration(tt.seconds)
		if got != tt.expected {
			t.Errorf("formatLockoutDuration(%d) = %q, want %q", tt.seconds, got, tt.expected)
		}
	}
}

// contains checks if a string contains a substring (case-insensitive not needed here).
func contains(s, substr string) bool {
	return len(s) >= len(substr) && searchString(s, substr)
}

func searchString(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
