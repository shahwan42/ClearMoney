// Integration tests that verify the database schema after all migrations run.
//
// These tests ensure that our SQL migration files actually create the expected
// tables, enums, foreign keys, and seed data in PostgreSQL. They act as a
// safety net — if someone writes a broken migration, these tests catch it.
//
// Laravel equivalent: testing that `php artisan migrate:fresh` produces the
// expected schema. You might write Feature tests that check Schema::hasTable().
// Django equivalent: testing that `python manage.py migrate` creates all models
// correctly. Django's test runner does this automatically with TestCase.
//
// Go testing pattern — table-driven vs. individual tests:
//   We use individual test functions (TestMigrations_XTableExists) rather than
//   a single test with a loop. This is intentional: each test appears separately
//   in the test output, making it easy to see exactly which table is missing.
//   Go's `go test -run TestMigrations_Accounts` lets you run specific tests.
//
// Go testing pattern — integration tests with real databases:
//   Unlike unit tests that use mocks, these tests hit a real PostgreSQL instance.
//   They're skipped when TEST_DATABASE_URL is not set (via getTestDatabaseURL).
//   Run them with: TEST_DATABASE_URL=postgres://... go test ./internal/database/ -v -p 1
//   The -p 1 flag runs tests sequentially (important when sharing a database).
//
// See: https://go.dev/blog/subtests — Go subtests and sub-benchmarks
package database

import (
	"database/sql"
	"testing"
)

// migratedDB is a test helper that returns a fully-migrated database connection.
//
// Go testing pattern — test fixture factory:
//   This is a setup helper that gives each test a ready-to-use database.
//   Laravel equivalent: RefreshDatabase trait or setUp() in TestCase.
//   Django equivalent:  TransactionTestCase.setUp() with fixtures.
//
// Note: unlike Laravel's RefreshDatabase which rolls back after each test,
// these migrations are additive — they run once and the schema persists.
// This is fine because migrations are idempotent (re-running them is a no-op).
//
// The caller is responsible for defer db.Close() to clean up the connection.
func migratedDB(t *testing.T) *sql.DB {
	t.Helper()
	url := getTestDatabaseURL(t)
	db, err := Connect(url)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	if err := RunMigrations(db); err != nil {
		t.Fatalf("migrations: %v", err)
	}
	return db
}

// assertTableExists is a reusable assertion that checks if a table exists.
//
// Go testing pattern — custom assertions:
//   Go doesn't have built-in assertion libraries like PHPUnit's $this->assertTrue()
//   or pytest's assert. Instead, you write small helper functions like this one.
//   The t.Helper() call ensures error messages point to the calling test, not here.
//
// SQL concept — information_schema:
//   information_schema is a standard SQL metadata catalog available in PostgreSQL,
//   MySQL, and SQL Server. It lets you query the database's own structure.
//   information_schema.tables lists all tables in the database.
//
// Go concept — parameterized queries with $1:
//   PostgreSQL uses $1, $2, etc. for parameterized queries (prevents SQL injection).
//   Laravel uses ? placeholders (or named :bindings).
//   Django's ORM handles this automatically, but raw queries use %s placeholders.
func assertTableExists(t *testing.T, db *sql.DB, table string) {
	t.Helper()
	var exists bool
	err := db.QueryRow(`SELECT EXISTS (
		SELECT FROM information_schema.tables WHERE table_name = $1
	)`, table).Scan(&exists)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if !exists {
		t.Errorf("expected table %q to exist", table)
	}
}

// --- Table existence tests ---
// Each test below verifies that a specific migration created its table.
// They map to our migration files: 000001_create_institutions.up.sql, etc.

func TestMigrations_InstitutionsTableExists(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()
	assertTableExists(t, db, "institutions")
}

func TestMigrations_AccountsTableExists(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()
	assertTableExists(t, db, "accounts")
}

func TestMigrations_CategoriesTableExists(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()
	assertTableExists(t, db, "categories")
}

func TestMigrations_PersonsTableExists(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()
	assertTableExists(t, db, "persons")
}

func TestMigrations_TransactionsTableExists(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()
	assertTableExists(t, db, "transactions")
}

func TestMigrations_ExchangeRateLogTableExists(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()
	assertTableExists(t, db, "exchange_rate_log")
}

// --- Enum tests ---
// PostgreSQL enums are custom types (like PHP enums or Python Enum classes).
// These tests verify that our migrations created the right enum types with
// the correct number of values.

// TestMigrations_AccountTypeEnum verifies the account_type PostgreSQL enum.
//
// SQL concept — pg_enum:
//   pg_enum is a PostgreSQL system catalog that stores enum values.
//   The ::regtype cast converts a type name string to a type OID for lookup.
//   This is PostgreSQL-specific — MySQL uses ENUM inline in column definitions.
//
// Laravel equivalent: checking that an enum column was created correctly.
// Django equivalent:  verifying a choices field or TextChoices enum.
func TestMigrations_AccountTypeEnum(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()

	var count int
	err := db.QueryRow(`SELECT COUNT(*) FROM pg_enum WHERE enumtypid = 'account_type'::regtype`).Scan(&count)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if count != 6 {
		t.Errorf("expected 6 account_type enum values, got %d", count)
	}
}

func TestMigrations_TransactionTypeEnum(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()

	var count int
	err := db.QueryRow(`SELECT COUNT(*) FROM pg_enum WHERE enumtypid = 'transaction_type'::regtype`).Scan(&count)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if count != 7 {
		t.Errorf("expected 7 transaction_type enum values, got %d", count)
	}
}

// TestMigrations_AccountsForeignKey verifies that the foreign key constraint
// between accounts and institutions was created correctly.
//
// SQL concept — information_schema.table_constraints:
//   This system view lists all constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK)
//   on all tables. We query it to verify our migration created the FK correctly.
//
// Laravel equivalent: checking that $table->foreignId('institution_id')->constrained()
// created the expected foreign key.
// Django equivalent:  verifying that a ForeignKey field created the DB constraint.
func TestMigrations_AccountsForeignKey(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()

	var exists bool
	err := db.QueryRow(`SELECT EXISTS (
		SELECT FROM information_schema.table_constraints
		WHERE constraint_type = 'FOREIGN KEY'
		AND table_name = 'accounts'
		AND constraint_name = 'accounts_institution_id_fkey'
	)`).Scan(&exists)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if !exists {
		t.Error("expected foreign key constraint on accounts.institution_id")
	}
}

// TestMigrations_DefaultCategoriesSeeded verifies that migration 000007 seeded
// the default expense and income categories.
//
// This tests a migration that contains both DDL (schema changes) and DML
// (data inserts). Our migration seeds system categories (is_system = true)
// so the app has default categories out of the box.
//
// Laravel equivalent: verifying that a seeder ran (like CategorySeeder).
// Django equivalent:  checking that a data migration populated initial data.
func TestMigrations_DefaultCategoriesSeeded(t *testing.T) {
	db := migratedDB(t)
	defer db.Close()

	var expenseCount, incomeCount int
	err := db.QueryRow(`SELECT COUNT(*) FROM categories WHERE type = 'expense' AND is_system = true`).Scan(&expenseCount)
	if err != nil {
		t.Fatalf("query expense: %v", err)
	}
	err = db.QueryRow(`SELECT COUNT(*) FROM categories WHERE type = 'income' AND is_system = true`).Scan(&incomeCount)
	if err != nil {
		t.Fatalf("query income: %v", err)
	}

	if expenseCount < 16 {
		t.Errorf("expected at least 16 expense categories, got %d", expenseCount)
	}
	if incomeCount < 7 {
		t.Errorf("expected at least 7 income categories, got %d", incomeCount)
	}
}
