// auth_test.go — Integration tests for the magic link auth service.
//
// Tests the core auth service methods:
//   - RequestLoginLink: rate limiting, token reuse, unknown email handling
//   - RequestRegistrationLink: duplicate prevention, rate limiting
//   - VerifyMagicLink: token validation, session creation
//   - ValidateSession: session lookup, expiry checking
//   - CleanupExpired: removes old tokens and sessions
//
// These are integration tests that run against a real PostgreSQL database.
package service

import (
	"context"
	"testing"

	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// setupMagicLinkTest creates all auth dependencies for testing.
func setupMagicLinkTest(t *testing.T) (*AuthService, *repository.UserRepo) {
	t.Helper()
	db := testutil.NewTestDB(t)
	ctx := context.Background()

	// Clean auth tables (order matters for foreign keys)
	db.ExecContext(ctx, "DELETE FROM sessions")
	db.ExecContext(ctx, "DELETE FROM auth_tokens")
	// Delete categories created by SeedDefaults for auth test users
	db.ExecContext(ctx, `DELETE FROM categories WHERE user_id IN (SELECT id FROM users WHERE email IN ('authtest@example.com', 'authnew@example.com'))`)
	db.ExecContext(ctx, "DELETE FROM users WHERE email IN ('authtest@example.com', 'authnew@example.com')")

	userRepo := repository.NewUserRepo(db)
	sessionRepo := repository.NewSessionRepo(db)
	tokenRepo := repository.NewAuthTokenRepo(db)
	emailSvc := NewEmailService("", "", "http://localhost:8080") // dev mode (no emails sent)
	categoryRepo := repository.NewCategoryRepo(db)
	authSvc := NewAuthService(userRepo, sessionRepo, tokenRepo, emailSvc, 50)
	authSvc.SetCategoryRepo(categoryRepo)

	return authSvc, userRepo
}

func TestRequestLoginLink_UnknownEmail(t *testing.T) {
	svc, _ := setupMagicLinkTest(t)
	ctx := context.Background()

	// Unknown email — should not error, but emailSent should be false
	sent, err := svc.RequestLoginLink(ctx, "unknown@example.com")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if sent {
		t.Error("expected emailSent=false for unknown email")
	}
}

func TestRequestLoginLink_ExistingUser(t *testing.T) {
	svc, userRepo := setupMagicLinkTest(t)
	ctx := context.Background()

	// Create a user first
	_, err := userRepo.Create(ctx, "authtest@example.com")
	if err != nil {
		t.Fatalf("creating user: %v", err)
	}

	// Known email — should send (dev mode logs instead)
	sent, err := svc.RequestLoginLink(ctx, "authtest@example.com")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !sent {
		t.Error("expected emailSent=true for known email")
	}
}

func TestRequestLoginLink_TokenReuse(t *testing.T) {
	svc, userRepo := setupMagicLinkTest(t)
	ctx := context.Background()

	_, err := userRepo.Create(ctx, "authtest@example.com")
	if err != nil {
		t.Fatalf("creating user: %v", err)
	}

	// First request — sends email
	sent1, err := svc.RequestLoginLink(ctx, "authtest@example.com")
	if err != nil {
		t.Fatalf("first request: %v", err)
	}
	if !sent1 {
		t.Error("expected first request to send email")
	}

	// Second request immediately — should reuse existing token (no email sent)
	sent2, err := svc.RequestLoginLink(ctx, "authtest@example.com")
	if err != nil {
		t.Fatalf("second request: %v", err)
	}
	if sent2 {
		t.Error("expected second request to NOT send email (token reuse)")
	}
}

func TestRequestRegistrationLink_NewEmail(t *testing.T) {
	svc, _ := setupMagicLinkTest(t)
	ctx := context.Background()

	sent, err := svc.RequestRegistrationLink(ctx, "authnew@example.com")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !sent {
		t.Error("expected emailSent=true for new registration")
	}
}

func TestRequestRegistrationLink_ExistingEmail(t *testing.T) {
	svc, userRepo := setupMagicLinkTest(t)
	ctx := context.Background()

	// Create a user first
	_, err := userRepo.Create(ctx, "authtest@example.com")
	if err != nil {
		t.Fatalf("creating user: %v", err)
	}

	// Attempt to register with existing email — should error
	_, err = svc.RequestRegistrationLink(ctx, "authtest@example.com")
	if err == nil {
		t.Error("expected error for duplicate registration")
	}
}

func TestVerifyMagicLink_LoginFlow(t *testing.T) {
	svc, userRepo := setupMagicLinkTest(t)
	ctx := context.Background()

	// Create user and request login link
	_, err := userRepo.Create(ctx, "authtest@example.com")
	if err != nil {
		t.Fatalf("creating user: %v", err)
	}

	svc.RequestLoginLink(ctx, "authtest@example.com")

	// Get the token from the DB
	db := testutil.NewTestDB(t)
	var token string
	err = db.QueryRowContext(ctx,
		"SELECT token FROM auth_tokens WHERE email = 'authtest@example.com' AND purpose = 'login' ORDER BY created_at DESC LIMIT 1",
	).Scan(&token)
	if err != nil {
		t.Fatalf("getting token: %v", err)
	}

	// Verify the token
	result, err := svc.VerifyMagicLink(ctx, token)
	if err != nil {
		t.Fatalf("verifying token: %v", err)
	}
	if result.SessionToken == "" {
		t.Error("expected session token")
	}
	if result.IsNewUser {
		t.Error("expected IsNewUser=false for login")
	}
}

func TestVerifyMagicLink_RegistrationFlow(t *testing.T) {
	svc, _ := setupMagicLinkTest(t)
	ctx := context.Background()

	svc.RequestRegistrationLink(ctx, "authnew@example.com")

	// Get the token from the DB
	db := testutil.NewTestDB(t)
	var token string
	err := db.QueryRowContext(ctx,
		"SELECT token FROM auth_tokens WHERE email = 'authnew@example.com' AND purpose = 'registration' ORDER BY created_at DESC LIMIT 1",
	).Scan(&token)
	if err != nil {
		t.Fatalf("getting token: %v", err)
	}

	// Verify the token
	result, err := svc.VerifyMagicLink(ctx, token)
	if err != nil {
		t.Fatalf("verifying token: %v", err)
	}
	if result.SessionToken == "" {
		t.Error("expected session token")
	}
	if !result.IsNewUser {
		t.Error("expected IsNewUser=true for registration")
	}
}

func TestVerifyMagicLink_InvalidToken(t *testing.T) {
	svc, _ := setupMagicLinkTest(t)
	ctx := context.Background()

	_, err := svc.VerifyMagicLink(ctx, "invalid-token")
	if err == nil {
		t.Error("expected error for invalid token")
	}
}

func TestValidateSession(t *testing.T) {
	svc, userRepo := setupMagicLinkTest(t)
	ctx := context.Background()

	// Create user and get a session via the full flow
	_, err := userRepo.Create(ctx, "authtest@example.com")
	if err != nil {
		t.Fatalf("creating user: %v", err)
	}

	svc.RequestLoginLink(ctx, "authtest@example.com")

	db := testutil.NewTestDB(t)
	var token string
	err = db.QueryRowContext(ctx,
		"SELECT token FROM auth_tokens WHERE email = 'authtest@example.com' ORDER BY created_at DESC LIMIT 1",
	).Scan(&token)
	if err != nil {
		t.Fatalf("getting token: %v", err)
	}

	result, err := svc.VerifyMagicLink(ctx, token)
	if err != nil {
		t.Fatalf("verifying token: %v", err)
	}

	// Validate the session
	userID, email, err := svc.ValidateSession(ctx, result.SessionToken)
	if err != nil {
		t.Fatalf("validating session: %v", err)
	}
	if userID == "" {
		t.Error("expected userID")
	}
	if email != "authtest@example.com" {
		t.Errorf("expected email authtest@example.com, got %s", email)
	}
}

func TestCleanupExpired(t *testing.T) {
	svc, _ := setupMagicLinkTest(t)
	ctx := context.Background()

	// This should not error even with no expired data
	svc.CleanupExpired(ctx)
}
