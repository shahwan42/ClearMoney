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
	"crypto/hmac"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"net/http"
	"testing"

	"github.com/shahwan42/clearmoney/internal/models"

	"golang.org/x/crypto/bcrypt"
)

// CreateInstitution inserts a test institution and returns it with its generated ID.
// Defaults to a bank named "Test Bank" — override by passing a modified struct.
//
// # The Override Pattern
//
// Go doesn't have named/optional parameters like Python (name="HSBC") or PHP
// ($name = 'HSBC'). Instead, we pass a struct and check for zero values:
//
//	// All defaults:
//	inst := CreateInstitution(t, db, models.Institution{})
//	// Override name only:
//	inst := CreateInstitution(t, db, models.Institution{Name: "HSBC"})
//	// Override multiple fields:
//	inst := CreateInstitution(t, db, models.Institution{Name: "HSBC", Type: "wallet"})
//
// This is idiomatic Go — the struct acts as a "parameter object" with optional fields.
// Unset string fields default to "" (Go's zero value), which we detect and replace
// with sensible defaults.
//
// # RETURNING Clause
//
// PostgreSQL's RETURNING clause returns the values of columns after the INSERT,
// including DB-generated values like id (UUID), created_at, and updated_at.
// This avoids a separate SELECT query. Laravel's create() does this automatically
// via Eloquent; in Go we must explicitly use RETURNING and Scan the results.
//
// See: https://www.postgresql.org/docs/current/dml-returning.html
func CreateInstitution(t *testing.T, db *sql.DB, inst models.Institution) models.Institution {
	t.Helper()

	// Apply defaults for required fields if not set.
	// Go's zero value for string is "" — we use this to detect "not provided."
	if inst.Name == "" {
		inst.Name = "Test Bank"
	}
	if inst.Type == "" {
		inst.Type = models.InstitutionTypeBank
	}

	// db.QueryRow executes an INSERT and scans the RETURNING values in one call.
	// This is like Laravel's `DB::table('institutions')->insertGetId(...)` or
	// Django's `Institution.objects.create(...)` which returns the created instance.
	err := db.QueryRow(`
		INSERT INTO institutions (name, type, color, icon, display_order)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, created_at, updated_at
	`, inst.Name, inst.Type, inst.Color, inst.Icon, inst.DisplayOrder,
	).Scan(&inst.ID, &inst.CreatedAt, &inst.UpdatedAt)

	if err != nil {
		t.Fatalf("creating test institution: %v", err)
	}

	return inst
}

// CreateAccount inserts a test account under the given institution.
// Defaults to EGP current account with 0 balance.
//
// Note: InstitutionID must be set (accounts have a foreign key to institutions).
// The current_balance is automatically set to initial_balance, mirroring the
// real application behavior where a new account starts with its initial balance.
//
// Example:
//
//	acc := testutil.CreateAccount(t, db, models.Account{
//	    InstitutionID: inst.ID,
//	    Name:          "Current",
//	    Currency:      models.CurrencyUSD,
//	    InitialBalance: 5000,
//	})
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
	// Set current_balance to initial_balance on creation (mirrors real behavior).
	// In the real app, TransactionService updates current_balance on each transaction.
	acc.CurrentBalance = acc.InitialBalance

	err := db.QueryRow(`
		INSERT INTO accounts (institution_id, name, type, currency, current_balance, initial_balance, credit_limit, is_dormant, display_order)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING id, created_at, updated_at
	`, acc.InstitutionID, acc.Name, acc.Type, acc.Currency,
		acc.CurrentBalance, acc.InitialBalance, acc.CreditLimit,
		acc.IsDormant, acc.DisplayOrder,
	).Scan(&acc.ID, &acc.CreatedAt, &acc.UpdatedAt)

	if err != nil {
		t.Fatalf("creating test account: %v", err)
	}

	return acc
}

// SetupAuth creates a test user with PIN "1234" and returns a session cookie.
// Use this to authenticate requests in handler tests.
//
// # Why This Doesn't Import middleware or service Packages
//
// This function re-implements the session token creation algorithm (HMAC-SHA256)
// directly instead of calling middleware.CreateSessionToken(). This is intentional:
// importing middleware from testutil would create an import cycle
// (testutil -> middleware -> service -> testutil). Go strictly forbids circular imports.
//
// In Laravel, you'd use `$this->actingAs($user)` which is built into the test framework.
// In Django, you'd use `self.client.force_login(user)`. Go has no built-in auth
// testing support, so we create the session manually.
//
// # How It Works
//
//  1. Truncates user_config to remove any existing PIN/session
//  2. Hashes "1234" with bcrypt (same as the real login flow)
//  3. Stores the hash and a fixed session key in user_config
//  4. Creates an HMAC token signed with the session key
//  5. Returns an http.Cookie that can be added to test requests
//
// Usage in handler tests:
//
//	cookie := testutil.SetupAuth(t, db)
//	req.AddCookie(cookie)  // adds auth to the request
//
// See: https://pkg.go.dev/golang.org/x/crypto/bcrypt
// See: https://pkg.go.dev/crypto/hmac
func SetupAuth(t *testing.T, db *sql.DB) *http.Cookie {
	t.Helper()
	ctx := context.Background()

	// Clean up any existing config — ensures a predictable state.
	db.ExecContext(ctx, "TRUNCATE TABLE user_config")

	// Hash PIN with bcrypt — the same algorithm used in the real login flow.
	// bcrypt is a one-way hash designed for passwords. It's slow by design
	// to resist brute-force attacks. bcrypt.DefaultCost = 10 (2^10 iterations).
	// See: https://pkg.go.dev/golang.org/x/crypto/bcrypt
	hash, err := bcrypt.GenerateFromPassword([]byte("1234"), bcrypt.DefaultCost)
	if err != nil {
		t.Fatalf("hashing pin: %v", err)
	}

	// Use a fixed session key for deterministic test tokens.
	// In production, the session key is randomly generated on first login.
	sessionKey := "test-session-key-for-integration-tests"

	_, err = db.ExecContext(ctx, `INSERT INTO user_config (pin_hash, session_key) VALUES ($1, $2)`,
		string(hash), sessionKey)
	if err != nil {
		t.Fatalf("inserting user_config: %v", err)
	}

	// Create session token (same algorithm as middleware.CreateSessionToken).
	// We duplicate this logic here to avoid import cycles.
	mac := hmac.New(sha256.New, []byte(sessionKey))
	mac.Write([]byte("session"))
	token := hex.EncodeToString(mac.Sum(nil))

	// Return an http.Cookie struct that can be added to test HTTP requests.
	// http.Cookie is Go's representation of an HTTP cookie — similar to
	// Symfony's Cookie class that Laravel uses under the hood.
	return &http.Cookie{
		Name:  "clearmoney_session",
		Value: token,
	}
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
		INSERT INTO virtual_accounts (name, target_amount, current_balance, icon, color, is_archived, display_order)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, created_at, updated_at
	`, va.Name, va.TargetAmount, va.CurrentBalance, va.Icon, va.Color, va.IsArchived, va.DisplayOrder,
	).Scan(&va.ID, &va.CreatedAt, &va.UpdatedAt)

	if err != nil {
		t.Fatalf("creating test virtual account: %v", err)
	}

	return va
}

// GetFirstCategoryID returns the ID of the first system category of the given type.
// Useful for creating test transactions that need a valid category_id FK reference,
// and for testing system category protection rules.
//
// Categories are seeded by migrations, so they're always available in the test DB.
// Filters to is_system = true to avoid returning custom categories created by
// other tests sharing the same database.
//
// Usage:
//
//	catID := testutil.GetFirstCategoryID(t, db, models.CategoryTypeExpense)
func GetFirstCategoryID(t *testing.T, db *sql.DB, categoryType models.CategoryType) string {
	t.Helper()
	var id string
	err := db.QueryRow(`SELECT id FROM categories WHERE type = $1 AND is_system = true LIMIT 1`, categoryType).Scan(&id)
	if err != nil {
		t.Fatalf("getting %s category: %v", categoryType, err)
	}
	return id
}
