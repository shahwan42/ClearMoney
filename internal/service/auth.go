// auth.go — AuthService handles magic-link authentication for ClearMoney.
//
// Authentication is passwordless: users enter their email, receive a magic link,
// click it, and get a server-side session. No passwords are ever stored.
//
// The auth flow:
//   1. User enters email on /login or /register
//   2. Server generates a crypto-random token, stores it in auth_tokens
//   3. Email with magic link is sent via Resend API
//   4. User clicks link → GET /auth/verify?token=xxx
//   5. Server validates token (not expired, not used, single-use)
//   6. Login: find existing user → create session
//      Registration: create user → seed categories → create session
//   7. Session cookie set (30-day expiry)
//
// Rate limiting (protects Resend free tier — 100 emails/day):
//   - Token reuse: if an unexpired token exists, don't send a new email
//   - Per-email cooldown: 1 email per 5 minutes per address
//   - Per-email daily: 3 emails per address per day
//   - Global daily cap: configurable MAX_DAILY_EMAILS (default 50)
//   - Login only sends to existing users (unknown emails = no email sent)
//
// Laravel analogy: Like a combined Auth + PasswordBroker but for magic links.
// Django analogy: Like django-sesame with custom rate limiting.
package service

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/shahwan42/clearmoney/internal/logutil"
	"github.com/shahwan42/clearmoney/internal/repository"
)

const (
	// SessionCookieName is the name of the auth session cookie.
	SessionCookieName = "clearmoney_session"

	// SessionMaxAge is how long sessions last (30 days).
	SessionMaxAge = 30 * 24 * time.Hour

	// tokenTTLMinutes is how long a magic link token is valid (15 minutes).
	tokenTTLMinutes = 15

	// emailCooldownMinutes is the per-email cooldown between magic link requests.
	emailCooldownMinutes = 5

	// maxDailyPerEmail is the max magic link emails per address per day.
	maxDailyPerEmail = 3
)

// SendResult describes the outcome of a magic link request.
// Used by handlers to decide what message to show the user.
//
// Laravel analogy: Like returning an enum from a Mail job — the caller checks
// the status to decide what flash message to show.
type SendResult int

const (
	SendResultSent       SendResult = iota // Email was sent successfully
	SendResultReused                       // Existing unexpired token — no new email
	SendResultCooldown                     // Per-email cooldown active (5 min)
	SendResultDailyLimit                   // Per-email daily limit reached (3/day)
	SendResultGlobalCap                    // Global daily email cap reached
	SendResultSkipped                      // Not sent (unknown email on login)
)

// AuthService handles magic-link authentication, sessions, and rate limiting.
type AuthService struct {
	userRepo       *repository.UserRepo
	sessionRepo    *repository.SessionRepo
	tokenRepo      *repository.AuthTokenRepo
	categoryRepo   *repository.CategoryRepo // seeds default categories for new users
	emailSvc       *EmailService
	maxDailyEmails int // global daily email cap (protects Resend free tier)
}

// NewAuthService creates a new auth service with all dependencies.
func NewAuthService(
	userRepo *repository.UserRepo,
	sessionRepo *repository.SessionRepo,
	tokenRepo *repository.AuthTokenRepo,
	emailSvc *EmailService,
	maxDailyEmails int,
) *AuthService {
	if maxDailyEmails <= 0 {
		maxDailyEmails = 50
	}
	return &AuthService{
		userRepo:       userRepo,
		sessionRepo:    sessionRepo,
		tokenRepo:      tokenRepo,
		emailSvc:       emailSvc,
		maxDailyEmails: maxDailyEmails,
	}
}

// SetCategoryRepo sets the category repo for seeding defaults on registration.
func (s *AuthService) SetCategoryRepo(repo *repository.CategoryRepo) {
	s.categoryRepo = repo
}

// RequestLoginLink sends a magic link to an existing user's email.
// If the email doesn't belong to a registered user, no email is sent — but the
// same "Check your email" response is shown (prevents email enumeration).
// Returns (SendResult, error). Any result other than SendResultSent means no email
// was sent (unknown user, rate limited, or token reuse) but is NOT an error —
// caller should still show "Check your email" page.
func (s *AuthService) RequestLoginLink(ctx context.Context, email string) (SendResult, error) {
	email = strings.TrimSpace(strings.ToLower(email))
	if email == "" {
		return SendResultSkipped, fmt.Errorf("email is required")
	}

	// Only send to existing users — unknown emails get the same UX (prevent enumeration)
	_, err := s.userRepo.GetByEmail(ctx, email)
	if errors.Is(err, sql.ErrNoRows) {
		slog.Info("login request for unknown email (no email sent)", "email", email)
		return SendResultSkipped, nil // not an error — just don't send
	}
	if err != nil {
		return SendResultSkipped, fmt.Errorf("checking user: %w", err)
	}

	return s.sendMagicLink(ctx, email, "login")
}

// RequestRegistrationLink sends a magic link for a new user registration.
// Returns an error if the email is already registered.
func (s *AuthService) RequestRegistrationLink(ctx context.Context, email string) (SendResult, error) {
	email = strings.TrimSpace(strings.ToLower(email))
	if email == "" {
		return SendResultSkipped, fmt.Errorf("email is required")
	}

	// Reject if already registered
	_, err := s.userRepo.GetByEmail(ctx, email)
	if err == nil {
		return SendResultSkipped, fmt.Errorf("an account with this email already exists")
	}
	if !errors.Is(err, sql.ErrNoRows) {
		return SendResultSkipped, fmt.Errorf("checking user: %w", err)
	}

	return s.sendMagicLink(ctx, email, "registration")
}

// sendMagicLink handles shared logic for both login and registration link requests.
// Applies rate limiting, token reuse, and sends the email.
func (s *AuthService) sendMagicLink(ctx context.Context, email, purpose string) (SendResult, error) {
	// Token reuse: if an unexpired token already exists, don't send a new email
	existingToken, err := s.tokenRepo.GetUnexpiredToken(ctx, email, purpose)
	if err == nil {
		if s.emailSvc.IsDevMode() {
			slog.Info("reusing existing token (dev mode)",
				"email", email,
				"link", s.emailSvc.LinkURL(existingToken),
			)
		} else {
			slog.Info("reusing existing token (no email sent)", "email", email, "purpose", purpose)
		}
		return SendResultReused, nil
	}
	if !errors.Is(err, sql.ErrNoRows) {
		return SendResultSkipped, fmt.Errorf("checking existing token: %w", err)
	}

	// Per-email cooldown: 1 per 5 minutes
	recentCount, err := s.tokenRepo.CountRecentByEmail(ctx, email, emailCooldownMinutes)
	if err != nil {
		return SendResultSkipped, fmt.Errorf("checking email cooldown: %w", err)
	}
	if recentCount > 0 {
		slog.Warn("email cooldown active (no email sent)", "email", email)
		return SendResultCooldown, nil
	}

	// Per-email daily limit: 3 per day
	dailyByEmail, err := s.tokenRepo.CountTodayByEmail(ctx, email)
	if err != nil {
		return SendResultSkipped, fmt.Errorf("checking daily email limit: %w", err)
	}
	if dailyByEmail >= maxDailyPerEmail {
		slog.Warn("daily per-email limit reached (no email sent)", "email", email, "count", dailyByEmail)
		return SendResultDailyLimit, nil
	}

	// Global daily cap
	globalCount, err := s.tokenRepo.CountToday(ctx)
	if err != nil {
		return SendResultSkipped, fmt.Errorf("checking global daily cap: %w", err)
	}
	if globalCount >= s.maxDailyEmails {
		slog.Error("global daily email cap reached", "count", globalCount, "max", s.maxDailyEmails)
		return SendResultGlobalCap, nil
	}

	// Generate token
	token, err := generateSecureToken()
	if err != nil {
		return SendResultSkipped, fmt.Errorf("generating token: %w", err)
	}

	// Store token in DB
	_, err = s.tokenRepo.Create(ctx, email, token, purpose, tokenTTLMinutes)
	if err != nil {
		return SendResultSkipped, fmt.Errorf("storing token: %w", err)
	}

	// Send email
	if err := s.emailSvc.SendMagicLink(ctx, email, token); err != nil {
		return SendResultSkipped, fmt.Errorf("sending email: %w", err)
	}

	logutil.LogEvent(ctx, "auth.magic_link_sent", "email", email, "purpose", purpose)
	return SendResultSent, nil
}

// VerifyResult holds the outcome of verifying a magic link token.
type VerifyResult struct {
	SessionToken string
	UserID       string
	IsNewUser    bool
}

// VerifyMagicLink validates a magic link token and creates a session.
// For login tokens: finds existing user → creates session.
// For registration tokens: creates user → creates session.
func (s *AuthService) VerifyMagicLink(ctx context.Context, token string) (VerifyResult, error) {
	token = strings.TrimSpace(token)
	if token == "" {
		return VerifyResult{}, fmt.Errorf("token is required")
	}

	// Look up token
	at, err := s.tokenRepo.GetByToken(ctx, token)
	if errors.Is(err, sql.ErrNoRows) {
		return VerifyResult{}, fmt.Errorf("invalid or expired link")
	}
	if err != nil {
		return VerifyResult{}, fmt.Errorf("looking up token: %w", err)
	}

	// Check if already used
	if at.Used {
		return VerifyResult{}, fmt.Errorf("this link has already been used")
	}

	// Check expiry
	if time.Now().After(at.ExpiresAt) {
		return VerifyResult{}, fmt.Errorf("this link has expired")
	}

	// Mark as used immediately (single-use)
	if err := s.tokenRepo.MarkUsed(ctx, at.ID); err != nil {
		return VerifyResult{}, fmt.Errorf("marking token used: %w", err)
	}

	var userID string
	var isNewUser bool

	switch at.Purpose {
	case "login":
		// Find existing user
		user, err := s.userRepo.GetByEmail(ctx, at.Email)
		if err != nil {
			return VerifyResult{}, fmt.Errorf("finding user: %w", err)
		}
		userID = user.ID

	case "registration":
		// Create new user
		user, err := s.userRepo.Create(ctx, at.Email)
		if err != nil {
			return VerifyResult{}, fmt.Errorf("creating user: %w", err)
		}
		userID = user.ID
		isNewUser = true

		// Seed default categories for the new user
		if s.categoryRepo != nil {
			if err := s.categoryRepo.SeedDefaults(ctx, userID); err != nil {
				slog.Error("failed to seed categories for new user", "user_id", userID, "error", err)
				// Non-fatal: user can still use the app, categories can be added manually
			}
		}

		logutil.LogEvent(ctx, "auth.user_registered", "email", at.Email)

	default:
		return VerifyResult{}, fmt.Errorf("unknown token purpose: %s", at.Purpose)
	}

	// Create session
	sessionToken, err := generateSecureToken()
	if err != nil {
		return VerifyResult{}, fmt.Errorf("generating session token: %w", err)
	}

	expiresAt := time.Now().Add(SessionMaxAge)
	_, err = s.sessionRepo.Create(ctx, userID, sessionToken, expiresAt)
	if err != nil {
		return VerifyResult{}, fmt.Errorf("creating session: %w", err)
	}

	logutil.LogEvent(ctx, "auth.login_success", "purpose", at.Purpose)

	return VerifyResult{
		SessionToken: sessionToken,
		UserID:       userID,
		IsNewUser:    isNewUser,
	}, nil
}

// ValidateSession checks if a session token is valid and returns the user ID and email.
// Called by the auth middleware on every protected request.
func (s *AuthService) ValidateSession(ctx context.Context, token string) (userID, email string, err error) {
	session, err := s.sessionRepo.GetByToken(ctx, token)
	if err != nil {
		return "", "", fmt.Errorf("invalid session: %w", err)
	}

	// Check expiry
	if time.Now().After(session.ExpiresAt) {
		// Clean up expired session
		_ = s.sessionRepo.DeleteByToken(ctx, token)
		return "", "", fmt.Errorf("session expired")
	}

	// Get user email for context
	user, err := s.userRepo.GetByID(ctx, session.UserID)
	if err != nil {
		return "", "", fmt.Errorf("user not found: %w", err)
	}

	return user.ID, user.Email, nil
}

// Logout deletes the session (server-side logout).
func (s *AuthService) Logout(ctx context.Context, token string) {
	if err := s.sessionRepo.DeleteByToken(ctx, token); err != nil {
		slog.Error("logout: failed to delete session", "error", err)
	}
	logutil.LogEvent(ctx, "auth.logout")
}

// CleanupExpired removes expired tokens and sessions.
// Called at startup and periodically.
func (s *AuthService) CleanupExpired(ctx context.Context) {
	tokenCount, err := s.tokenRepo.DeleteExpired(ctx)
	if err != nil {
		slog.Error("cleanup: failed to delete expired tokens", "error", err)
	} else if tokenCount > 0 {
		slog.Info("cleanup: deleted expired auth tokens", "count", tokenCount)
	}

	sessionCount, err := s.sessionRepo.DeleteExpired(ctx)
	if err != nil {
		slog.Error("cleanup: failed to delete expired sessions", "error", err)
	} else if sessionCount > 0 {
		slog.Info("cleanup: deleted expired sessions", "count", sessionCount)
	}
}

// generateSecureToken creates a cryptographically secure random token.
// Uses 32 bytes (256 bits) of entropy, encoded as URL-safe base64.
func generateSecureToken() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", fmt.Errorf("generating random bytes: %w", err)
	}
	return base64.URLEncoding.EncodeToString(b), nil
}
