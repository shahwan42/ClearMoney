package database

import (
	"database/sql"
	"testing"
)

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
