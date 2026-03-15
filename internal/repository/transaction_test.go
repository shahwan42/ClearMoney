// Integration tests for TransactionRepo.
//
// Transaction tests are more complex than institution/account tests because
// transactions have foreign keys to accounts, institutions, and categories.
// The setup function creates the full dependency chain.
//
// Key testing patterns demonstrated here:
//   - t.Helper() for setup functions (error line numbers point to callers)
//   - Table cleaning order matters for foreign key constraints
//   - DB transactions (BeginTx/Commit/Rollback) tested explicitly
//   - defer dbTx.Rollback() is safe even after Commit (Rollback on committed tx is a no-op)
//
// See: https://pkg.go.dev/testing
package repository

import (
	"context"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// setupTransactionTest creates a clean test environment with an institution,
// account, and both repos needed for transaction testing.
//
// Tables are cleaned in reverse-dependency order: transactions first (depends on
// accounts), accounts second (depends on institutions), institutions last.
// This respects foreign key constraints.
//   Laravel:  This is like DatabaseMigrations::setUp() with truncation
//   Django:   This is like TransactionTestCase with flush
func setupTransactionTest(t *testing.T) (*TransactionRepo, *AccountRepo, models.Account) {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Test Bank"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeCurrent,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	return NewTransactionRepo(db), NewAccountRepo(db), acc
}

// TestTransactionRepo_Create verifies basic transaction creation with a category.
// testutil.GetFirstCategoryID fetches a seeded system category from the DB.
func TestTransactionRepo_Create(t *testing.T) {
	txRepo, _, acc := setupTransactionTest(t)
	catID := testutil.GetFirstCategoryID(t, txRepo.db, models.CategoryTypeExpense)

	created, err := txRepo.Create(context.Background(), models.Transaction{
		Type:      models.TransactionTypeExpense,
		Amount:    250.50,
		Currency:  models.CurrencyEGP,
		AccountID: acc.ID,
		CategoryID: &catID,
		Date:      time.Now(),
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if created.ID == "" {
		t.Error("expected ID to be set")
	}
	if created.Amount != 250.50 {
		t.Errorf("expected amount 250.50, got %f", created.Amount)
	}
}

// TestTransactionRepo_CreateTx tests creation within a database transaction.
//
// The `defer dbTx.Rollback()` is a safety net: if the test fails before Commit(),
// the transaction is rolled back automatically. After Commit(), Rollback() is a no-op.
// This is a critical Go pattern for DB transactions — always defer Rollback.
//
//   Laravel:  DB::transaction(fn () => ...);  // auto-rollback on exception
//   Django:   with transaction.atomic(): ...  // auto-rollback on exception
//   Go:       defer dbTx.Rollback()           // explicit safety net
func TestTransactionRepo_CreateTx(t *testing.T) {
	txRepo, _, acc := setupTransactionTest(t)

	dbTx, err := txRepo.BeginTx(context.Background())
	if err != nil {
		t.Fatalf("begin tx: %v", err)
	}
	defer dbTx.Rollback()

	created, err := txRepo.CreateTx(context.Background(), dbTx, models.Transaction{
		Type:      models.TransactionTypeIncome,
		Amount:    5000,
		Currency:  models.CurrencyEGP,
		AccountID: acc.ID,
	})
	if err != nil {
		t.Fatalf("create tx: %v", err)
	}
	if err := dbTx.Commit(); err != nil {
		t.Fatalf("commit: %v", err)
	}
	if created.ID == "" {
		t.Error("expected ID to be set")
	}
}

func TestTransactionRepo_GetByID(t *testing.T) {
	txRepo, _, acc := setupTransactionTest(t)
	note := "Grocery shopping"

	created, _ := txRepo.Create(context.Background(), models.Transaction{
		Type:      models.TransactionTypeExpense,
		Amount:    150,
		Currency:  models.CurrencyEGP,
		AccountID: acc.ID,
		Note:      &note,
	})

	found, err := txRepo.GetByID(context.Background(), created.ID)
	if err != nil {
		t.Fatalf("get by id: %v", err)
	}
	if found.Amount != 150 {
		t.Errorf("expected 150, got %f", found.Amount)
	}
	if found.Note == nil || *found.Note != "Grocery shopping" {
		t.Error("expected note 'Grocery shopping'")
	}
}

func TestTransactionRepo_GetRecent(t *testing.T) {
	txRepo, _, acc := setupTransactionTest(t)

	// Create 3 transactions
	for i := 0; i < 3; i++ {
		txRepo.Create(context.Background(), models.Transaction{
			Type:      models.TransactionTypeExpense,
			Amount:    float64(100 * (i + 1)),
			Currency:  models.CurrencyEGP,
			AccountID: acc.ID,
		})
	}

	recent, err := txRepo.GetRecent(context.Background(), 2)
	if err != nil {
		t.Fatalf("get recent: %v", err)
	}
	if len(recent) != 2 {
		t.Errorf("expected 2 transactions, got %d", len(recent))
	}
}

func TestTransactionRepo_GetByAccount(t *testing.T) {
	txRepo, _, acc := setupTransactionTest(t)

	txRepo.Create(context.Background(), models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 100,
		Currency: models.CurrencyEGP, AccountID: acc.ID,
	})
	txRepo.Create(context.Background(), models.Transaction{
		Type: models.TransactionTypeIncome, Amount: 200,
		Currency: models.CurrencyEGP, AccountID: acc.ID,
	})

	txns, err := txRepo.GetByAccount(context.Background(), acc.ID, 10)
	if err != nil {
		t.Fatalf("get by account: %v", err)
	}
	if len(txns) != 2 {
		t.Errorf("expected 2, got %d", len(txns))
	}
}

func TestTransactionRepo_Delete(t *testing.T) {
	txRepo, _, acc := setupTransactionTest(t)

	created, _ := txRepo.Create(context.Background(), models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 500,
		Currency: models.CurrencyEGP, AccountID: acc.ID,
	})

	err := txRepo.Delete(context.Background(), created.ID)
	if err != nil {
		t.Fatalf("delete: %v", err)
	}

	_, err = txRepo.GetByID(context.Background(), created.ID)
	if err == nil {
		t.Error("expected error after deletion")
	}
}

// TestTransactionRepo_UpdateBalanceTx verifies that balance updates within a
// DB transaction are atomic — the balance change is only visible after Commit.
func TestTransactionRepo_UpdateBalanceTx(t *testing.T) {
	txRepo, accRepo, acc := setupTransactionTest(t)

	dbTx, err := txRepo.BeginTx(context.Background())
	if err != nil {
		t.Fatalf("begin tx: %v", err)
	}
	defer dbTx.Rollback()

	// Subtract 3000 from balance (simulating expense)
	if err := txRepo.UpdateBalanceTx(context.Background(), dbTx, acc.ID, -3000); err != nil {
		t.Fatalf("update balance: %v", err)
	}
	if err := dbTx.Commit(); err != nil {
		t.Fatalf("commit: %v", err)
	}

	updated, _ := accRepo.GetByID(context.Background(), acc.ID)
	if updated.CurrentBalance != 7000 {
		t.Errorf("expected 7000, got %f", updated.CurrentBalance)
	}
}
