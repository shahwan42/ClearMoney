// Integration tests for AccountRepo.
//
// These tests use a real PostgreSQL database, which is the standard Go integration
// test pattern. Unlike Laravel's RefreshDatabase that wraps each test in a transaction,
// we manually clean tables before each test.
//
// Test fixtures (testutil.CreateInstitution, etc.) are factory functions similar to
// Laravel's model factories or Django's baker/factory_boy.
package repository

import (
	"context"
	"testing"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// setupAccountTest is a test helper that creates a clean environment.
//
// t.Helper() marks this function as a test helper — when a test fails inside
// this function, Go reports the line number of the CALLER, not this function.
// Like PHPUnit's setUp() method, but called explicitly.
//
// Returns: the AccountRepo, a pre-created Institution, and the test user ID.
func setupAccountTest(t *testing.T) (*AccountRepo, models.Institution, string) {
	t.Helper()
	db := testutil.NewTestDB(t)
	userID := testutil.SetupTestUser(t, db)
	testutil.CleanTable(t, db, "institutions")
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC", UserID: userID})
	return NewAccountRepo(db), inst, userID
}

// TestAccountRepo_Create verifies that creating an account sets current_balance = initial_balance
// and auto-generates an ID.
func TestAccountRepo_Create(t *testing.T) {
	repo, inst, userID := setupAccountTest(t)

	acc, err := repo.Create(context.Background(), userID, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeCurrent,
		Currency:       models.CurrencyEGP,
		InitialBalance: 100000,
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if acc.ID == "" {
		t.Error("expected ID")
	}
	if acc.CurrentBalance != 100000 {
		t.Errorf("expected balance 100000, got %f", acc.CurrentBalance)
	}
}

// TestAccountRepo_Create_CreditCard verifies credit card accounts store their credit_limit.
// The credit_limit is a *float64 (pointer) because it's nullable — only credit cards have one.
// In Go, a nil pointer means "not set" (like NULL in SQL, None in Python, null in PHP).
func TestAccountRepo_Create_CreditCard(t *testing.T) {
	repo, inst, userID := setupAccountTest(t)
	limit := 500000.0

	acc, err := repo.Create(context.Background(), userID, models.Account{
		InstitutionID: inst.ID,
		Name:          "Credit Card",
		Type:          models.AccountTypeCreditCard,
		Currency:      models.CurrencyEGP,
		CreditLimit:   &limit,
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if acc.CreditLimit == nil || *acc.CreditLimit != 500000 {
		t.Error("expected credit limit 500000")
	}
}

func TestAccountRepo_GetByID(t *testing.T) {
	repo, inst, userID := setupAccountTest(t)

	created, _ := repo.Create(context.Background(), userID, models.Account{
		InstitutionID: inst.ID,
		Name:          "Savings",
		Type:          models.AccountTypeSavings,
		Currency:      models.CurrencyUSD,
	})

	found, err := repo.GetByID(context.Background(), userID, created.ID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if found.Name != "Savings" {
		t.Errorf("expected Savings, got %q", found.Name)
	}
	if found.Currency != models.CurrencyUSD {
		t.Errorf("expected USD, got %q", found.Currency)
	}
}

func TestAccountRepo_GetByInstitution(t *testing.T) {
	repo, inst, userID := setupAccountTest(t)

	repo.Create(context.Background(), userID, models.Account{
		InstitutionID: inst.ID, Name: "Checking", Type: models.AccountTypeCurrent, Currency: models.CurrencyEGP,
	})
	repo.Create(context.Background(), userID, models.Account{
		InstitutionID: inst.ID, Name: "Savings", Type: models.AccountTypeSavings, Currency: models.CurrencyEGP,
	})

	accounts, err := repo.GetByInstitution(context.Background(), userID, inst.ID)
	if err != nil {
		t.Fatalf("get by institution: %v", err)
	}
	if len(accounts) != 2 {
		t.Errorf("expected 2 accounts, got %d", len(accounts))
	}
}

// TestAccountRepo_UpdateBalance verifies atomic balance updates.
// Tests both positive (income) and negative (expense) deltas to ensure
// the SQL arithmetic `current_balance = current_balance + $delta` works correctly.
func TestAccountRepo_UpdateBalance(t *testing.T) {
	repo, inst, userID := setupAccountTest(t)

	acc, _ := repo.Create(context.Background(), userID, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Test",
		Type:           models.AccountTypeCurrent,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	// Add 5000
	err := repo.UpdateBalance(context.Background(), userID, acc.ID, 5000)
	if err != nil {
		t.Fatalf("update balance: %v", err)
	}

	updated, _ := repo.GetByID(context.Background(), userID, acc.ID)
	if updated.CurrentBalance != 15000 {
		t.Errorf("expected 15000, got %f", updated.CurrentBalance)
	}

	// Subtract 3000
	repo.UpdateBalance(context.Background(), userID, acc.ID, -3000)
	updated, _ = repo.GetByID(context.Background(), userID, acc.ID)
	if updated.CurrentBalance != 12000 {
		t.Errorf("expected 12000, got %f", updated.CurrentBalance)
	}
}

// TestAccountRepo_Create_Cash verifies cash accounts can be created under a wallet institution.
func TestAccountRepo_Create_Cash(t *testing.T) {
	db := testutil.NewTestDB(t)
	userID := testutil.SetupTestUser(t, db)
	testutil.CleanTable(t, db, "institutions")
	wallet := testutil.CreateInstitution(t, db, models.Institution{
		Name:   "Cash",
		Type:   models.InstitutionTypeWallet,
		UserID: userID,
	})
	repo := NewAccountRepo(db)

	acc, err := repo.Create(context.Background(), userID, models.Account{
		InstitutionID:  wallet.ID,
		Name:           "EGP Cash",
		Type:           models.AccountTypeCash,
		Currency:       models.CurrencyEGP,
		InitialBalance: 3500,
	})
	if err != nil {
		t.Fatalf("create cash account: %v", err)
	}
	if acc.ID == "" {
		t.Error("expected ID")
	}
	if acc.Type != models.AccountTypeCash {
		t.Errorf("expected type cash, got %q", acc.Type)
	}
	if acc.CurrentBalance != 3500 {
		t.Errorf("expected balance 3500, got %f", acc.CurrentBalance)
	}
	if acc.CreditLimit != nil {
		t.Error("cash account should not have credit limit")
	}
}

func TestAccountRepo_Delete(t *testing.T) {
	repo, inst, userID := setupAccountTest(t)

	acc, _ := repo.Create(context.Background(), userID, models.Account{
		InstitutionID: inst.ID, Name: "To Delete",
		Type: models.AccountTypeCurrent, Currency: models.CurrencyEGP,
	})

	err := repo.Delete(context.Background(), userID, acc.ID)
	if err != nil {
		t.Fatalf("delete: %v", err)
	}

	_, err = repo.GetByID(context.Background(), userID, acc.ID)
	if err == nil {
		t.Error("expected error after deletion")
	}
}
