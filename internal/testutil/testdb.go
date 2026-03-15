// Package testutil provides shared helpers for integration tests.
//
// # Purpose
//
// This package is the Go equivalent of:
//   - Laravel:  The RefreshDatabase trait + DatabaseMigrations trait + model factories.
//               In Laravel, you'd use `use RefreshDatabase` in your test class to get
//               a clean, migrated database for each test.
//   - Django:   TestCase (which wraps tests in transactions) + fixtures/factory_boy.
//               Django's TestCase provides cls.setUpClass() for database setup.
//
// # Why a Separate Package?
//
// Go organizes test helpers in a dedicated package (internal/testutil/) rather
// than a base test class. This is because Go doesn't have class inheritance —
// there's no "extends TestCase" like PHPUnit or unittest.TestCase. Instead,
// test helpers are plain functions that accept *testing.T as their first argument.
//
// The `internal/` prefix means this package can only be imported by code within
// this module — it's Go's way of making packages "private." External packages
// cannot import internal/testutil, which is perfect for test helpers.
//
// # Usage Pattern
//
//	func TestSomething(t *testing.T) {
//	    db := testutil.NewTestDB(t)       // connects, migrates, auto-closes
//	    testutil.CleanTable(t, db, "accounts")  // ensure clean state
//	    acc := testutil.CreateAccount(t, db, models.Account{Name: "Test"})
//	    // ... test logic using acc and db ...
//	}
//
// See: https://pkg.go.dev/testing
// See: https://go.dev/doc/tutorial/add-a-test
package testutil

import (
	"database/sql"
	"os"
	"testing"

	"github.com/shahwan42/clearmoney/internal/database"
)

// NewTestDB creates a database connection for integration tests.
// It automatically:
//  1. Skips the test if TEST_DATABASE_URL is not set
//  2. Connects to the database
//  3. Runs all migrations
//  4. Registers a cleanup function to close the connection when the test ends
//
// # Key Go Testing Concepts Used
//
// t.Helper():
//
//	Marks this function as a test helper. When a test fails inside a helper,
//	Go reports the line number of the CALLER, not the helper itself. Without
//	t.Helper(), error messages would point to this file instead of the test
//	that called NewTestDB. This is like PHPUnit marking a method as @internal
//	so stack traces skip it.
//
// t.Skip():
//
//	Marks the test as "skipped" (not "failed") and stops execution. The test
//	appears in output as "SKIP" with a reason. This is perfect for integration
//	tests that require external dependencies — if the database URL isn't set,
//	we skip gracefully instead of failing. Similar to PHPUnit's markTestSkipped()
//	or pytest's pytest.mark.skipIf.
//
// t.Fatalf():
//
//	Logs an error message and immediately stops the test. Use this for
//	unrecoverable setup errors where continuing would cause panics or
//	misleading failures. Similar to PHPUnit's $this->fail() or pytest.fail().
//
// t.Cleanup():
//
//	Registers a function that runs after the test completes (pass or fail).
//	Multiple cleanup functions run in LIFO order (last registered, first called).
//	This is Go's equivalent of:
//	  - PHPUnit:  tearDown() method
//	  - Django:   addCleanup() or tearDown()
//	  - pytest:   yield-based fixtures or request.addfinalizer()
//	Unlike tearDown(), t.Cleanup() is scoped to the helper that registers it,
//	so the test function doesn't need to know about cleanup details.
//
// See: https://pkg.go.dev/testing#T.Helper
// See: https://pkg.go.dev/testing#T.Skip
// See: https://pkg.go.dev/testing#T.Cleanup
func NewTestDB(t *testing.T) *sql.DB {
	t.Helper() // marks this as a helper so error line numbers point to the caller

	// Read the test database URL from the environment.
	// os.Getenv returns "" if the variable is not set (no error).
	// This is like Laravel's env('TEST_DATABASE_URL') or Django's os.environ.get().
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("TEST_DATABASE_URL not set, skipping integration test")
	}

	// Connect to the test database using the same connection logic as production.
	// database.Connect wraps sql.Open + db.Ping to verify the connection works.
	db, err := database.Connect(url)
	if err != nil {
		t.Fatalf("connecting to test database: %v", err)
	}

	// Run all migrations to ensure the schema is up to date.
	// Migrations are idempotent — they skip if already applied.
	// If migrations fail, close the DB to avoid leaking connections.
	if err := database.RunMigrations(db); err != nil {
		db.Close()
		t.Fatalf("running migrations: %v", err)
	}

	// Re-seed system categories if they were truncated by a previous test run
	// (e.g., e2e resetDatabase). Migration 000007 seeds them once, but if the
	// categories table gets truncated, the migration won't re-run since it's
	// already tracked in schema_migrations.
	ensureSeedCategories(t, db)

	// t.Cleanup registers a function that runs when this test finishes.
	// This ensures db.Close() is called even if the test panics.
	// The connection is returned to the caller, who uses it for the test,
	// and Go automatically closes it when the test completes.
	t.Cleanup(func() {
		db.Close()
	})

	return db
}

// ensureSeedCategories re-inserts system categories if they're missing.
//
// Migration 000007 seeds categories, but only runs once. If e2e tests or other
// processes truncate the categories table, the migration won't re-run because
// it's already tracked in schema_migrations. This function checks for missing
// system categories and re-inserts them.
//
// Uses INSERT ... ON CONFLICT DO NOTHING to be idempotent — safe to call
// multiple times without creating duplicates.
func ensureSeedCategories(t *testing.T, db *sql.DB) {
	t.Helper()

	var count int
	if err := db.QueryRow(`SELECT COUNT(*) FROM categories WHERE is_system = true`).Scan(&count); err != nil {
		t.Fatalf("checking system categories: %v", err)
	}
	if count >= 25 {
		return // already seeded (18 expense + 7 income)
	}

	// Re-seed using the same data as migration 000007 + icons from 000019.
	_, err := db.Exec(`
		INSERT INTO categories (name, type, icon, is_system, display_order) VALUES
			('Household',        'expense', '🏠', true, 1),
			('Food & Groceries', 'expense', '🛒', true, 2),
			('Transport',        'expense', '🚗', true, 3),
			('Health',           'expense', '🏥', true, 4),
			('Education',        'expense', '📚', true, 5),
			('Mobile',           'expense', '📱', true, 6),
			('Electricity',      'expense', '⚡', true, 7),
			('Gas',              'expense', '🔥', true, 8),
			('Internet',         'expense', '🌐', true, 9),
			('Gifts',            'expense', '🎁', true, 10),
			('Entertainment',    'expense', '🎬', true, 11),
			('Shopping',         'expense', '🛍️', true, 12),
			('Subscriptions',    'expense', '📺', true, 13),
			('Virtual Account',  'expense', '🏦', true, 14),
			('Insurance',        'expense', '🛡️', true, 15),
			('Fees & Charges',   'expense', '💳', true, 16),
			('Debt Payment',     'expense', '💰', true, 17),
			('Other',            'expense', '🔖', true, 18),
			('Salary',                    'income', '💵', true, 1),
			('Freelance',                 'income', '💻', true, 2),
			('Investment Returns',        'income', '📈', true, 3),
			('Refund',                    'income', '🔄', true, 4),
			('Virtual Account',           'income', '🏦', true, 5),
			('Loan Repayment Received',   'income', '🤝', true, 6),
			('Other',                     'income', '💎', true, 7)
		ON CONFLICT (name, type) DO NOTHING
	`)
	if err != nil {
		t.Fatalf("re-seeding system categories: %v", err)
	}
}

// CleanTable deletes all rows from the given table.
// Useful for ensuring a clean state before inserting test data.
//
// # Why TRUNCATE Instead of DELETE?
//
// TRUNCATE is faster than DELETE for removing all rows because it doesn't
// generate individual row-level undo logs. CASCADE removes related rows in
// child tables (e.g., truncating accounts also removes their transactions).
// RESTART IDENTITY resets auto-increment sequences (serial columns) to 1.
//
// In Laravel, this is like `DB::table('accounts')->truncate()`.
// In Django, this is like `call_command('flush', '--no-input')` for a single table.
//
// Note: The table name is passed as a string and concatenated into SQL.
// This is safe here because table names come from our test code (not user input),
// but in general, never concatenate user-supplied values into SQL strings.
//
// Usage:
//
//	testutil.CleanTable(t, db, "transactions")
//	testutil.CleanTable(t, db, "accounts")
func CleanTable(t *testing.T, db *sql.DB, table string) {
	t.Helper()
	_, err := db.Exec("TRUNCATE TABLE " + table + " RESTART IDENTITY CASCADE")
	if err != nil {
		t.Fatalf("cleaning table %s: %v", table, err)
	}
}
