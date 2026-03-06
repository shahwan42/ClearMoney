package database

import (
	"testing"
)

func TestMigrations_InstitutionsTableExists(t *testing.T) {
	url := getTestDatabaseURL(t)
	db, err := Connect(url)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer db.Close()

	if err := RunMigrations(db); err != nil {
		t.Fatalf("migrations: %v", err)
	}

	var exists bool
	err = db.QueryRow(`SELECT EXISTS (
		SELECT FROM information_schema.tables WHERE table_name = 'institutions'
	)`).Scan(&exists)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if !exists {
		t.Error("expected institutions table to exist")
	}
}

func TestMigrations_AccountsTableExists(t *testing.T) {
	url := getTestDatabaseURL(t)
	db, err := Connect(url)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer db.Close()

	if err := RunMigrations(db); err != nil {
		t.Fatalf("migrations: %v", err)
	}

	var exists bool
	err = db.QueryRow(`SELECT EXISTS (
		SELECT FROM information_schema.tables WHERE table_name = 'accounts'
	)`).Scan(&exists)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if !exists {
		t.Error("expected accounts table to exist")
	}
}

func TestMigrations_AccountTypeEnum(t *testing.T) {
	url := getTestDatabaseURL(t)
	db, err := Connect(url)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer db.Close()

	if err := RunMigrations(db); err != nil {
		t.Fatalf("migrations: %v", err)
	}

	// Verify enum values exist
	var count int
	err = db.QueryRow(`SELECT COUNT(*) FROM pg_enum WHERE enumtypid = 'account_type'::regtype`).Scan(&count)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if count != 6 {
		t.Errorf("expected 6 account_type enum values, got %d", count)
	}
}

func TestMigrations_AccountsForeignKey(t *testing.T) {
	url := getTestDatabaseURL(t)
	db, err := Connect(url)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer db.Close()

	if err := RunMigrations(db); err != nil {
		t.Fatalf("migrations: %v", err)
	}

	var exists bool
	err = db.QueryRow(`SELECT EXISTS (
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
