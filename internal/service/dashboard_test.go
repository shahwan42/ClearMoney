package service

import (
	"context"
	"testing"
	"time"

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

func TestDashboardService_GetDashboard_USDConversion(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "exchange_rate_log")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	rateRepo := repository.NewExchangeRateRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)
	svc.SetExchangeRateRepo(rateRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "EGP Checking",
		Currency: models.CurrencyEGP, InitialBalance: 100000,
	})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD Savings",
		Currency: models.CurrencyUSD, InitialBalance: 2000,
	})

	// Log an exchange rate
	rateRepo.Log(context.Background(), time.Now(), 50.0, nil, nil)

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	// USD total = 2000
	if data.USDTotal != 2000 {
		t.Errorf("USDTotal = %f, want 2000", data.USDTotal)
	}

	// Exchange rate = 50
	if data.ExchangeRate != 50 {
		t.Errorf("ExchangeRate = %f, want 50", data.ExchangeRate)
	}

	// USD in EGP = 2000 * 50 = 100000
	if data.USDInEGP != 100000 {
		t.Errorf("USDInEGP = %f, want 100000", data.USDInEGP)
	}

	// NetWorthEGP = (102000 - 2000) + 100000 = 200000
	// (raw net worth is 100000 + 2000 = 102000, replace USD with EGP equivalent)
	if data.NetWorthEGP != 200000 {
		t.Errorf("NetWorthEGP = %f, want 200000", data.NetWorthEGP)
	}
}

func TestDashboardService_GetDashboard_NoExchangeRate(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "exchange_rate_log")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	rateRepo := repository.NewExchangeRateRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)
	svc.SetExchangeRateRepo(rateRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD Savings",
		Currency: models.CurrencyUSD, InitialBalance: 1000,
	})

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	// No exchange rate logged, so NetWorthEGP should be 0
	if data.ExchangeRate != 0 {
		t.Errorf("ExchangeRate = %f, want 0", data.ExchangeRate)
	}
	if data.NetWorthEGP != 0 {
		t.Errorf("NetWorthEGP = %f, want 0 (no rate)", data.NetWorthEGP)
	}
}
