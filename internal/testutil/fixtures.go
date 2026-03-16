// Fixtures provides factory functions for creating test data in the database.
//
// # Factory Pattern Comparison: Go vs Laravel vs Django
//
// Laravel factories:
//
//	// Define: database/factories/InstitutionFactory.php
//	Institution::factory()->definition() returns ['name' => fake()->company()];
//	// Use:
//	$inst = Institution::factory()->create(['name' => 'HSBC']);
//
// Django factory_boy:
//
//	// Define: tests/factories.py
//	class InstitutionFactory(factory.django.DjangoModelFactory):
//	    name = factory.Faker('company')
//	// Use:
//	inst = InstitutionFactory(name='HSBC')
//
// Go (this package):
//
//	// Define: internal/testutil/fixtures.go (this file)
//	func CreateInstitution(t, db, models.Institution{overrides}) models.Institution
//	// Use:
//	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
//
// Key differences:
//   - Go factories are plain functions, not classes with inheritance
//   - Defaults are applied via zero-value checks (if name == "" { name = "Test Bank" })
//   - Go's zero values (0 for numbers, "" for strings, false for bools) make it easy
//     to detect which fields were explicitly set vs left at defaults
//   - Each factory inserts into the real database and returns the model with DB-generated
//     fields (ID, timestamps) populated via RETURNING clause
//   - t.Helper() ensures error stack traces point to the test, not the factory
//   - t.Fatalf() stops the test on factory failure (can't continue without test data)
//
// See: https://go.dev/ref/spec#The_zero_value (Go's zero value concept)
package testutil

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"net/http"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
)

// SetupTestUser creates a test user (or finds existing) and returns the user ID.
// Call this before creating institutions, accounts, etc. since all tables require user_id.
func SetupTestUser(t *testing.T, db *sql.DB) string {
	t.Helper()
	ctx := context.Background()

	// Try to find existing test user first
	var userID string
	err := db.QueryRowContext(ctx, `SELECT id FROM users WHERE email = 'test@example.com'`).Scan(&userID)
	if err == nil {
		return userID
	}

	// Create new test user
	err = db.QueryRowContext(ctx, `INSERT INTO users (email) VALUES ('test@example.com') RETURNING id`).Scan(&userID)
	if err != nil {
		t.Fatalf("creating test user: %v", err)
	}
	return userID
}

// CreateInstitution inserts a test institution and returns it with its generated ID.
// Defaults to a bank named "Test Bank" — override by passing a modified struct.
// The model's UserID field must be set (call SetupTestUser first).
func CreateInstitution(t *testing.T, db *sql.DB, inst models.Institution) models.Institution {
	t.Helper()

	if inst.Name == "" {
		inst.Name = "Test Bank"
	}
	if inst.Type == "" {
		inst.Type = models.InstitutionTypeBank
	}

	err := db.QueryRow(`
		INSERT INTO institutions (name, type, color, icon, display_order, user_id)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, created_at, updated_at
	`, inst.Name, inst.Type, inst.Color, inst.Icon, inst.DisplayOrder, inst.UserID,
	).Scan(&inst.ID, &inst.CreatedAt, &inst.UpdatedAt)

	if err != nil {
		t.Fatalf("creating test institution: %v", err)
	}

	return inst
}

// CreateAccount inserts a test account under the given institution.
// Defaults to EGP current account with 0 balance.
func CreateAccount(t *testing.T, db *sql.DB, acc models.Account) models.Account {
	t.Helper()

	if acc.Name == "" {
		acc.Name = "Test Account"
	}
	if acc.Type == "" {
		acc.Type = models.AccountTypeCurrent
	}
	if acc.Currency == "" {
		acc.Currency = models.CurrencyEGP
	}
	acc.CurrentBalance = acc.InitialBalance

	err := db.QueryRow(`
		INSERT INTO accounts (institution_id, name, type, currency, current_balance, initial_balance, credit_limit, is_dormant, display_order, user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING id, created_at, updated_at
	`, acc.InstitutionID, acc.Name, acc.Type, acc.Currency,
		acc.CurrentBalance, acc.InitialBalance, acc.CreditLimit,
		acc.IsDormant, acc.DisplayOrder, acc.UserID,
	).Scan(&acc.ID, &acc.CreatedAt, &acc.UpdatedAt)

	if err != nil {
		t.Fatalf("creating test account: %v", err)
	}

	return acc
}

// SetupAuth creates a test user and a DB session, returning a session cookie.
// Use this to authenticate requests in handler tests.
//
// The new auth system uses server-side DB sessions (not HMAC tokens). This function:
//  1. Creates a user with email "test@example.com" in the users table
//  2. Creates a session row in the sessions table with a random token
//  3. Returns an http.Cookie containing the session token
//
// Also creates a user_config row for backward compatibility with code that still
// checks user_config (will be removed once migration is complete).
//
// Usage in handler tests:
//
//	cookie := testutil.SetupAuth(t, db)
//	req.AddCookie(cookie)  // adds auth to the request
func SetupAuth(t *testing.T, db *sql.DB) *http.Cookie {
	t.Helper()
	cookie, _ := SetupAuthWithUserID(t, db)
	return cookie
}

// CreateVirtualAccount inserts a test virtual account and returns it with its generated ID.
// Defaults to an active account named "Test Fund" with teal color.
func CreateVirtualAccount(t *testing.T, db *sql.DB, va models.VirtualAccount) models.VirtualAccount {
	t.Helper()

	if va.Name == "" {
		va.Name = "Test Fund"
	}
	if va.Color == "" {
		va.Color = "#0d9488"
	}

	err := db.QueryRow(`
		INSERT INTO virtual_accounts (name, target_amount, current_balance, icon, color, is_archived, display_order, account_id, exclude_from_net_worth, user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING id, created_at, updated_at
	`, va.Name, va.TargetAmount, va.CurrentBalance, va.Icon, va.Color, va.IsArchived, va.DisplayOrder, va.AccountID, va.ExcludeFromNetWorth, va.UserID,
	).Scan(&va.ID, &va.CreatedAt, &va.UpdatedAt)

	if err != nil {
		t.Fatalf("creating test virtual account: %v", err)
	}

	return va
}

// SetupAuthWithUserID is like SetupAuth but also returns the user ID for use in service/repo tests.
func SetupAuthWithUserID(t *testing.T, db *sql.DB) (*http.Cookie, string) {
	t.Helper()
	ctx := context.Background()

	// Reuse the idempotent SetupTestUser (finds existing or creates new)
	userID := SetupTestUser(t, db)

	// Create a fresh session for this test
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		t.Fatalf("generating session token: %v", err)
	}
	token := base64.URLEncoding.EncodeToString(b)

	_, err := db.ExecContext(ctx, `INSERT INTO sessions (user_id, token, expires_at) VALUES ($1, $2, $3)`,
		userID, token, time.Now().Add(30*24*time.Hour))
	if err != nil {
		t.Fatalf("creating test session: %v", err)
	}

	return &http.Cookie{Name: "clearmoney_session", Value: token}, userID
}

// SeedCategories inserts the default system categories for the given user.
// Call this in tests that need categories (e.g., category listing, transaction creation).
func SeedCategories(t *testing.T, db *sql.DB, userID string) {
	t.Helper()
	_, err := db.Exec(`
		INSERT INTO categories (user_id, name, type, icon, is_system, display_order) VALUES
			($1, 'Household', 'expense', '🏠', true, 1),
			($1, 'Food & Groceries', 'expense', '🛒', true, 2),
			($1, 'Transportation', 'expense', '🚗', true, 3),
			($1, 'Utilities & Bills', 'expense', '💡', true, 4),
			($1, 'Healthcare', 'expense', '🏥', true, 5),
			($1, 'Education', 'expense', '📚', true, 6),
			($1, 'Entertainment', 'expense', '🎬', true, 7),
			($1, 'Shopping & Clothing', 'expense', '👗', true, 8),
			($1, 'Personal Care', 'expense', '💇', true, 9),
			($1, 'Dining Out', 'expense', '🍽️', true, 10),
			($1, 'Travel', 'expense', '✈️', true, 11),
			($1, 'Insurance', 'expense', '🛡️', true, 12),
			($1, 'Gifts & Donations', 'expense', '🎁', true, 13),
			($1, 'Subscriptions', 'expense', '📱', true, 14),
			($1, 'Home Maintenance', 'expense', '🔧', true, 15),
			($1, 'Pets', 'expense', '🐾', true, 16),
			($1, 'Kids', 'expense', '👶', true, 17),
			($1, 'Other', 'expense', '📦', true, 18),
			($1, 'Salary', 'income', '💰', true, 1),
			($1, 'Freelance', 'income', '💻', true, 2),
			($1, 'Investment Returns', 'income', '📈', true, 3),
			($1, 'Rental Income', 'income', '🏘️', true, 4),
			($1, 'Gifts Received', 'income', '🎀', true, 5),
			($1, 'Refunds', 'income', '↩️', true, 6),
			($1, 'Other', 'income', '💎', true, 7)
		ON CONFLICT DO NOTHING
	`, userID)
	if err != nil {
		t.Fatalf("seeding categories: %v", err)
	}
}

// GetFirstCategoryID returns the ID of the first system category of the given type for the test user.
// Useful for creating test transactions that need a valid category_id FK reference.
// Seeds categories automatically if none exist for the test user.
func GetFirstCategoryID(t *testing.T, db *sql.DB, categoryType models.CategoryType) string {
	t.Helper()
	userID := SetupTestUser(t, db)

	var id string
	err := db.QueryRow(`SELECT id FROM categories WHERE type = $1 AND user_id = $2 AND is_system = true LIMIT 1`, categoryType, userID).Scan(&id)
	if err != nil {
		// No categories yet — seed them and retry
		SeedCategories(t, db, userID)
		err = db.QueryRow(`SELECT id FROM categories WHERE type = $1 AND user_id = $2 AND is_system = true LIMIT 1`, categoryType, userID).Scan(&id)
		if err != nil {
			t.Fatalf("getting %s category after seeding: %v", categoryType, err)
		}
	}
	return id
}
