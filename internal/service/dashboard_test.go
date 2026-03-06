package service

import (
	"context"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func TestDashboardService_GetDashboard(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)

	// Create test data
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Type:           models.AccountTypeSavings,
		Currency:       models.CurrencyEGP,
		InitialBalance: 100000,
	})

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	// Net worth = 50000 + 100000 = 150000
	if data.NetWorth != 150000 {
		t.Errorf("expected net worth 150000, got %f", data.NetWorth)
	}
	if data.CashTotal != 150000 {
		t.Errorf("expected cash 150000, got %f", data.CashTotal)
	}
	if len(data.Institutions) != 1 {
		t.Errorf("expected 1 institution, got %d", len(data.Institutions))
	}
	if len(data.Institutions[0].Accounts) != 2 {
		t.Errorf("expected 2 accounts, got %d", len(data.Institutions[0].Accounts))
	}
}

func TestDashboardService_GetDashboard_WithCredit(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeChecking,
		Currency:       models.CurrencyEGP,
		InitialBalance: 80000,
	})

	limit := 500000.0
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Credit Card",
		Type:           models.AccountTypeCreditCard,
		Currency:       models.CurrencyEGP,
		InitialBalance: -120000, // owes 120K
		CreditLimit:    &limit,
	})

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	// Net worth = 80000 + (-120000) = -40000
	if data.NetWorth != -40000 {
		t.Errorf("expected net worth -40000, got %f", data.NetWorth)
	}
	if data.CashTotal != 80000 {
		t.Errorf("expected cash 80000, got %f", data.CashTotal)
	}
	if data.CreditUsed != -120000 {
		t.Errorf("expected credit used -120000, got %f", data.CreditUsed)
	}
}

func TestDashboardService_GetDashboard_Empty(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	if data.NetWorth != 0 {
		t.Errorf("expected 0 net worth, got %f", data.NetWorth)
	}
	if len(data.Institutions) != 0 {
		t.Errorf("expected 0 institutions, got %d", len(data.Institutions))
	}
}
