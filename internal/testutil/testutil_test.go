// testutil_test.go — Tests for the test helpers themselves.
//
// # Why Test the Test Helpers?
//
// This might seem circular ("who tests the tests?"), but it's important because:
//
//  1. Test helpers are shared infrastructure — many tests depend on them.
//     A bug in CreateAccount could cause false passes or failures across
//     dozens of tests, making them very hard to debug.
//
//  2. These tests verify the "contract" of each helper:
//     - NewTestDB returns a working database connection
//     - CreateInstitution applies defaults correctly
//     - CreateAccount sets current_balance = initial_balance
//     - CleanTable actually removes all rows
//
// In Laravel, you'd rarely test RefreshDatabase because it's framework code.
// But our helpers are hand-written, so they deserve coverage just like any
// other code. This is a Go best practice: test helpers are code too.
//
// # Same-Package Testing
//
// This file is in package `testutil` (not `testutil_test`), which means it can
// access unexported (lowercase) functions and variables directly. Go allows
// two package names in test files:
//
//   - `package testutil`      — "white box" tests, can access private internals
//   - `package testutil_test` — "black box" tests, can only use exported API
//
// We use white-box testing here because our helpers are tightly integrated
// with the test database setup.
//
// See: https://go.dev/doc/tutorial/add-a-test
// See: https://pkg.go.dev/testing
package testutil

import (
	"testing"

	"github.com/shahwan42/clearmoney/internal/models"
)

// TestNewTestDB verifies that the test database helper returns a working connection.
// This is the most fundamental test — if this fails, all other integration tests
// would also fail, so we test it first to establish the foundation.
//
// The "SELECT 1" query is a minimal connectivity check (a "ping" query).
// PostgreSQL, MySQL, and SQLite all support it. It verifies:
//   - The connection string is valid
//   - The database server is reachable
//   - Migrations ran successfully (if they fail, NewTestDB calls t.Fatalf)
func TestNewTestDB(t *testing.T) {
	db := NewTestDB(t)

	// Verify we can query the database with a trivial SELECT
	var result int
	err := db.QueryRow("SELECT 1").Scan(&result)
	if err != nil {
		t.Fatalf("query failed: %v", err)
	}
	if result != 1 {
		t.Errorf("expected 1, got %d", result)
	}
}

// TestCreateInstitution_Defaults verifies that CreateInstitution applies
// sensible defaults when given an empty struct (zero values).
// This is the Go equivalent of testing Laravel's factory defaults:
//
//	$inst = Institution::factory()->create(); // uses all defaults
//	$this->assertEquals('Test Bank', $inst->name);
func TestCreateInstitution_Defaults(t *testing.T) {
	db := NewTestDB(t)
	CleanTable(t, db, "institutions")

	// Pass an empty struct — all fields use zero values.
	// Go's zero value for string is "", for int is 0, for bool is false.
	// Our factory detects "" and replaces it with a default.
	inst := CreateInstitution(t, db, models.Institution{})

	if inst.ID == "" {
		t.Error("expected institution to have an ID")
	}
	if inst.Name != "Test Bank" {
		t.Errorf("expected default name 'Test Bank', got %q", inst.Name)
	}
	if inst.Type != models.InstitutionTypeBank {
		t.Errorf("expected default type 'bank', got %q", inst.Type)
	}
}

// TestCreateInstitution_CustomValues verifies that explicitly provided
// fields override the defaults. This is like Laravel's:
//
//	$inst = Institution::factory()->create(['name' => 'HSBC']);
func TestCreateInstitution_CustomValues(t *testing.T) {
	db := NewTestDB(t)
	CleanTable(t, db, "institutions")

	inst := CreateInstitution(t, db, models.Institution{
		Name: "HSBC",
		Type: models.InstitutionTypeBank,
	})

	if inst.Name != "HSBC" {
		t.Errorf("expected name 'HSBC', got %q", inst.Name)
	}
}

// TestCreateAccount verifies the account factory creates an account with
// the correct initial and current balance, and links it to an institution.
func TestCreateAccount(t *testing.T) {
	db := NewTestDB(t)
	CleanTable(t, db, "institutions")

	// Create the parent institution first (accounts have a FK to institutions).
	// This dependency chain is explicit in Go, unlike Laravel where you might
	// use Institution::factory()->has(Account::factory()) for nested creation.
	inst := CreateInstitution(t, db, models.Institution{Name: "CIB"})

	acc := CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Type:           models.AccountTypeSavings,
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})

	if acc.ID == "" {
		t.Error("expected account to have an ID")
	}
	// Verify current_balance was set to initial_balance (factory contract)
	if acc.CurrentBalance != 50000 {
		t.Errorf("expected current_balance 50000, got %f", acc.CurrentBalance)
	}
	if acc.InstitutionID != inst.ID {
		t.Error("expected account to belong to the institution")
	}
}

// TestCreateAccount_CreditCard verifies that the factory handles pointer
// fields (CreditLimit is *float64) correctly. In Go, pointer fields are used
// for nullable database columns — nil means NULL, a pointer-to-value means
// the column has data. This is different from Laravel where nullable columns
// are simply null/non-null, and Django where they're None/value.
func TestCreateAccount_CreditCard(t *testing.T) {
	db := NewTestDB(t)
	CleanTable(t, db, "institutions")

	inst := CreateInstitution(t, db, models.Institution{})
	// &limit takes the address of the variable, creating a *float64 pointer.
	// This is Go's way of saying "this field has a value" vs nil (no value/NULL).
	limit := 500000.0

	acc := CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID,
		Name:          "HSBC Credit Card",
		Type:          models.AccountTypeCreditCard,
		CreditLimit:   &limit,
	})

	// Check both that the pointer is non-nil AND that the value is correct.
	if acc.CreditLimit == nil || *acc.CreditLimit != 500000 {
		t.Error("expected credit limit of 500000")
	}
}

// TestGetFirstCategoryID verifies we can retrieve seeded categories.
// Categories are populated by database migrations (seed data), so they
// should always be available in the test database.
func TestGetFirstCategoryID(t *testing.T) {
	db := NewTestDB(t)

	expenseID := GetFirstCategoryID(t, db, models.CategoryTypeExpense)
	if expenseID == "" {
		t.Error("expected to find an expense category")
	}

	incomeID := GetFirstCategoryID(t, db, models.CategoryTypeIncome)
	if incomeID == "" {
		t.Error("expected to find an income category")
	}

	// Expense and income categories should be different rows with different IDs
	if expenseID == incomeID {
		t.Error("expense and income category IDs should be different")
	}
}

// TestCleanTable verifies that CleanTable actually removes all rows.
// This is a critical helper — if it doesn't work, tests might pollute each
// other with leftover data, causing flaky failures.
func TestCleanTable(t *testing.T) {
	db := NewTestDB(t)

	// Create some data that should be removed
	CreateInstitution(t, db, models.Institution{Name: "To Be Deleted"})

	// Clean it
	CleanTable(t, db, "institutions")

	// Verify it's gone — assertDatabaseMissing() in Laravel terms
	var count int
	db.QueryRow("SELECT COUNT(*) FROM institutions").Scan(&count)
	if count != 0 {
		t.Errorf("expected 0 institutions after clean, got %d", count)
	}
}
