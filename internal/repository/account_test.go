package repository

import (
	"context"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func setupAccountTest(t *testing.T) (*AccountRepo, models.Institution) {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	return NewAccountRepo(db), inst
}

func TestAccountRepo_Create(t *testing.T) {
	repo, inst := setupAccountTest(t)

	acc, err := repo.Create(context.Background(), models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
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

func TestAccountRepo_Create_CreditCard(t *testing.T) {
	repo, inst := setupAccountTest(t)
	limit := 500000.0

	acc, err := repo.Create(context.Background(), models.Account{
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
	repo, inst := setupAccountTest(t)

	created, _ := repo.Create(context.Background(), models.Account{
		InstitutionID: inst.ID,
		Name:          "Savings",
		Type:          models.AccountTypeSavings,
		Currency:      models.CurrencyUSD,
	})

	found, err := repo.GetByID(context.Background(), created.ID)
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
	repo, inst := setupAccountTest(t)

	repo.Create(context.Background(), models.Account{
		InstitutionID: inst.ID, Name: "Checking", Type: models.AccountTypeChecking, Currency: models.CurrencyEGP,
	})
	repo.Create(context.Background(), models.Account{
		InstitutionID: inst.ID, Name: "Savings", Type: models.AccountTypeSavings, Currency: models.CurrencyEGP,
	})

	accounts, err := repo.GetByInstitution(context.Background(), inst.ID)
	if err != nil {
		t.Fatalf("get by institution: %v", err)
	}
	if len(accounts) != 2 {
		t.Errorf("expected 2 accounts, got %d", len(accounts))
	}
}

func TestAccountRepo_UpdateBalance(t *testing.T) {
	repo, inst := setupAccountTest(t)

	acc, _ := repo.Create(context.Background(), models.Account{
		InstitutionID:  inst.ID,
		Name:           "Test",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})

	// Add 5000
	err := repo.UpdateBalance(context.Background(), acc.ID, 5000)
	if err != nil {
		t.Fatalf("update balance: %v", err)
	}

	updated, _ := repo.GetByID(context.Background(), acc.ID)
	if updated.CurrentBalance != 15000 {
		t.Errorf("expected 15000, got %f", updated.CurrentBalance)
	}

	// Subtract 3000
	repo.UpdateBalance(context.Background(), acc.ID, -3000)
	updated, _ = repo.GetByID(context.Background(), acc.ID)
	if updated.CurrentBalance != 12000 {
		t.Errorf("expected 12000, got %f", updated.CurrentBalance)
	}
}

func TestAccountRepo_Delete(t *testing.T) {
	repo, inst := setupAccountTest(t)

	acc, _ := repo.Create(context.Background(), models.Account{
		InstitutionID: inst.ID, Name: "To Delete",
		Type: models.AccountTypeChecking, Currency: models.CurrencyEGP,
	})

	err := repo.Delete(context.Background(), acc.ID)
	if err != nil {
		t.Fatalf("delete: %v", err)
	}

	_, err = repo.GetByID(context.Background(), acc.ID)
	if err == nil {
		t.Error("expected error after deletion")
	}
}
