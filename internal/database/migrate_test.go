package database

import (
	"database/sql"
	"testing"
)

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

func TestRunMigrations_NilDB(t *testing.T) {
	err := RunMigrations(nil)
	if err == nil {
		t.Error("expected error for nil db, got nil")
	}
}

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

// cleanupMigrations drops the schema_migrations table to reset state between tests.
func cleanupMigrations(t *testing.T, db *sql.DB) {
	t.Helper()
	_, _ = db.Exec("DROP TABLE IF EXISTS schema_migrations")
}
