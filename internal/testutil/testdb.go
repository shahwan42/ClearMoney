// Package testutil provides shared helpers for integration tests.
//
// This is the Go equivalent of Laravel's RefreshDatabase trait or Django's
// TestCase class — it sets up a clean database for each test.
//
// Usage in tests:
//
//	func TestSomething(t *testing.T) {
//	    db := testutil.NewTestDB(t)  // connects, runs migrations, cleans up after
//	    // ... use db to run queries ...
//	}
//
// The test DB uses the TEST_DATABASE_URL environment variable.
// If it's not set, the test is skipped (not failed).
package testutil

import (
	"database/sql"
	"os"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/database"
)

// NewTestDB creates a database connection for integration tests.
// It automatically:
//  1. Skips the test if TEST_DATABASE_URL is not set
//  2. Connects to the database
//  3. Runs all migrations
//  4. Registers a cleanup function to close the connection when the test ends
//
// This is similar to Laravel's RefreshDatabase trait — each test gets
// a fully migrated database. We don't reset between tests because
// migrations are idempotent (they skip if already applied).
func NewTestDB(t *testing.T) *sql.DB {
	t.Helper() // marks this as a helper so error line numbers point to the caller

	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("TEST_DATABASE_URL not set, skipping integration test")
	}

	db, err := database.Connect(url)
	if err != nil {
		t.Fatalf("connecting to test database: %v", err)
	}

	if err := database.RunMigrations(db); err != nil {
		db.Close()
		t.Fatalf("running migrations: %v", err)
	}

	// t.Cleanup registers a function that runs when this test finishes.
	// Like Laravel's tearDown() or Django's addCleanup().
	t.Cleanup(func() {
		db.Close()
	})

	return db
}

// CleanTable deletes all rows from the given table.
// Useful for ensuring a clean state before inserting test data.
//
//	testutil.CleanTable(t, db, "transactions")
//	testutil.CleanTable(t, db, "accounts")
func CleanTable(t *testing.T, db *sql.DB, table string) {
	t.Helper()
	// Using TRUNCATE with CASCADE to also clean related tables.
	// RESTART IDENTITY resets auto-increment sequences.
	_, err := db.Exec("TRUNCATE TABLE " + table + " RESTART IDENTITY CASCADE")
	if err != nil {
		t.Fatalf("cleaning table %s: %v", table, err)
	}
}
