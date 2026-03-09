// Tests for the migration runner (RunMigrations).
//
// These are integration tests that verify our SQL migrations actually work
// against a real PostgreSQL database. They cover four key scenarios:
//
//  1. Idempotency — running migrations twice doesn't error (ErrNoChange is handled)
//  2. Side effects — the schema_migrations tracking table gets created
//  3. Nil safety — nil *sql.DB is handled gracefully
//  4. Closed connection — attempting migrations on a closed DB returns an error
//
// Go testing pattern — shared helpers across test files:
//   getTestDatabaseURL() is defined in database_test.go but usable here because
//   both files are in the same package ("package database"). In Go, all _test.go
//   files in the same package share access to each other's unexported symbols.
//   This is unlike PHP where each test class is isolated, or Python where each
//   test module is independent.
//
// See: https://go.dev/doc/code#Testing — how Go discovers and runs tests
package database

import (
	"database/sql"
	"testing"
)

// TestRunMigrations_NoMigrations verifies that running migrations is idempotent.
//
// "Idempotent" means running it multiple times produces the same result.
// This test effectively runs migrations twice (the DB may already have them
// from a previous test run) and checks that it doesn't error.
//
// This is important because our app calls RunMigrations on every startup —
// it must gracefully handle "nothing to do" (migrate.ErrNoChange).
func TestRunMigrations_NoMigrations(t *testing.T) {
	url := getTestDatabaseURL(t)

	db, err := Connect(url)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer db.Close()

	// Should succeed even with no migration files
	err = RunMigrations(db)
	if err != nil {
		t.Fatalf("expected no error with empty migrations, got %v", err)
	}
}

// TestRunMigrations_AppliesMigrations verifies that golang-migrate creates
// its tracking table (schema_migrations) after running migrations.
//
// Go concept — db.QueryRow().Scan():
//   This is how you execute a SQL query and read the result in Go's database/sql.
//   QueryRow runs a query expected to return at most one row, and Scan copies
//   the column values into Go variables (passed by pointer with &).
//
//   Laravel equivalent: DB::selectOne('SELECT EXISTS(...)')->exists
//   Django equivalent:  connection.cursor().execute('SELECT EXISTS(...)')
//
//   See: https://pkg.go.dev/database/sql#DB.QueryRow
//
// The information_schema query checks PostgreSQL's metadata catalog to confirm
// the schema_migrations table was created. This is a standard SQL approach to
// introspecting database structure.
func TestRunMigrations_AppliesMigrations(t *testing.T) {
	url := getTestDatabaseURL(t)

	db, err := Connect(url)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer db.Close()

	err = RunMigrations(db)
	if err != nil {
		t.Fatalf("migrations failed: %v", err)
	}

	// Verify the schema_migrations table exists (created by golang-migrate)
	var exists bool
	err = db.QueryRow(`SELECT EXISTS (
		SELECT FROM information_schema.tables
		WHERE table_name = 'schema_migrations'
	)`).Scan(&exists)
	if err != nil {
		t.Fatalf("query failed: %v", err)
	}
	if !exists {
		t.Error("expected schema_migrations table to exist")
	}
}

// TestRunMigrations_NilDB verifies that passing nil doesn't panic.
//
// Go testing pattern — nil safety test:
//   In Go, calling a method on a nil pointer causes a panic (runtime crash).
//   We explicitly guard against nil at the top of RunMigrations and return
//   a clean error instead. This test ensures that guard works.
//
//   In PHP, this would be like testing that a method handles null gracefully
//   instead of throwing a NullPointerException. In Python, like catching
//   AttributeError on None.
func TestRunMigrations_NilDB(t *testing.T) {
	err := RunMigrations(nil)
	if err == nil {
		t.Error("expected error for nil db, got nil")
	}
}

// TestRunMigrations_ClosedDB verifies that a closed connection is detected.
//
// Notice db.Close() is called WITHOUT defer — intentionally closing the
// connection before passing it to RunMigrations. This tests that the migration
// library properly detects and reports the closed connection.
func TestRunMigrations_ClosedDB(t *testing.T) {
	url := getTestDatabaseURL(t)

	db, err := Connect(url)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	db.Close()

	err = RunMigrations(db)
	if err == nil {
		t.Error("expected error for closed db, got nil")
	}
}

// cleanupMigrations is a test helper that drops the schema_migrations table.
//
// This resets the migration tracking state so tests can start fresh.
// The _, _ discards both return values (result and error) because we don't
// care if the DROP fails (the table might not exist yet, and that's fine).
//
// Go concept — multiple return values:
//   Go functions often return (result, error). The blank identifier _ discards
//   a return value you don't need. Unlike PHP/Python where you just ignore
//   the return, Go requires you to explicitly acknowledge each return value.
func cleanupMigrations(t *testing.T, db *sql.DB) {
	t.Helper()
	_, _ = db.Exec("DROP TABLE IF EXISTS schema_migrations")
}
