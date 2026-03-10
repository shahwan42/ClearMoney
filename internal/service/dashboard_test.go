// Tests for DashboardService — verifies the aggregated dashboard data.
//
// These integration tests check that the dashboard correctly computes:
// - Net worth from multiple accounts
// - Cash vs credit breakdown
// - USD conversion with exchange rates
// - People ledger summary
// - Building fund balance
//
// Each test creates a minimal set of fixtures, calls GetDashboard(), and verifies
// specific fields. The tests are independent — each one cleans the DB and creates
// its own data. Like Laravel's RefreshDatabase trait.
//
// Note: these tests don't exercise all 10+ data sources (snapshots, budgets, etc.)
// because those optional services are nil. The dashboard handles nil services gracefully.
package service

import (
	"context"
	"testing"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

// TestDashboardService_GetDashboard verifies the basic net worth calculation
// with two debit accounts under one institution.
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
		Type:           models.AccountTypeCurrent,
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

// TestDashboardService_GetDashboard_WithCredit tests net worth with credit cards.
// Credit card balances are negative (money owed), so they reduce net worth.
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
		Type:           models.AccountTypeCurrent,
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

// TestDashboardService_GetDashboard_Empty verifies the dashboard handles zero data gracefully.
// This is a boundary test — ensures no panics or errors when there are no institutions/accounts.
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

// TestDashboardService_GetDashboard_USDConversion tests multi-currency net worth.
// Demonstrates setter injection in action: svc.SetExchangeRateRepo(rateRepo) adds
// the optional exchange rate dependency. Without it, USD values appear raw.
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

func TestDashboardService_GetDashboard_CreditAvailable(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	limit := 100000.0
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "CC", Type: models.AccountTypeCreditCard,
		Currency: models.CurrencyEGP, InitialBalance: -30000, CreditLimit: &limit,
	})

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	if data.CreditAvail != 70000 {
		t.Errorf("CreditAvail = %f, want 70000", data.CreditAvail)
	}
}

// TestDashboardService_GetDashboard_PeopleSummary verifies the people ledger aggregation.
// Positive net_balance = they owe me, negative = I owe them.
func TestDashboardService_GetDashboard_PeopleSummary(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "persons")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	personRepo := repository.NewPersonRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)
	svc.SetPersonRepo(personRepo)

	// Create people with different net balances
	personRepo.Create(context.Background(), models.Person{Name: "Alice", NetBalance: 5000})   // owes me
	personRepo.Create(context.Background(), models.Person{Name: "Bob", NetBalance: -3000})     // I owe

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	if data.PeopleOwedToMe != 5000 {
		t.Errorf("PeopleOwedToMe = %f, want 5000", data.PeopleOwedToMe)
	}
	if data.PeopleIOwe != -3000 {
		t.Errorf("PeopleIOwe = %f, want -3000", data.PeopleIOwe)
	}
}

func TestDashboardService_GetDashboard_BuildingFund(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Main", Currency: models.CurrencyEGP, InitialBalance: 100000,
	})

	// Create building fund transactions
	txSvc := NewTransactionService(txRepo, accRepo)
	txSvc.Create(context.Background(), models.Transaction{
		Type: models.TransactionTypeIncome, Amount: 10000,
		Currency: models.CurrencyEGP, AccountID: acc.ID, IsBuildingFund: true,
	})
	txSvc.Create(context.Background(), models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 3000,
		Currency: models.CurrencyEGP, AccountID: acc.ID, IsBuildingFund: true,
	})
	// Non-building-fund transaction should not count
	txSvc.Create(context.Background(), models.Transaction{
		Type: models.TransactionTypeIncome, Amount: 50000,
		Currency: models.CurrencyEGP, AccountID: acc.ID, IsBuildingFund: false,
	})

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	// Building fund = 10000 (income) - 3000 (expense) = 7000
	if data.BuildingFundBalance != 7000 {
		t.Errorf("BuildingFundBalance = %f, want 7000", data.BuildingFundBalance)
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

// TestDashboardService_InstitutionTotal_ConvertsCurrency verifies that institution
// totals convert USD accounts to EGP using the exchange rate, rather than summing
// raw values across currencies. Regression test for BUG-005.
func TestDashboardService_InstitutionTotal_ConvertsCurrency(t *testing.T) {
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
		InstitutionID: inst.ID, Name: "EGP Savings",
		Currency: models.CurrencyEGP, InitialBalance: 47850,
	})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD Savings",
		Currency: models.CurrencyUSD, InitialBalance: 2100,
	})

	// Log exchange rate: 1 USD = 50 EGP
	source := "test"
	rateRepo.Log(context.Background(), time.Now(), 50.0, &source, nil)

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	// Institution total should be 47850 + (2100 * 50) = 47850 + 105000 = 152850
	if len(data.Institutions) == 0 {
		t.Fatal("expected at least one institution")
	}
	expectedTotal := 47850.0 + 2100.0*50.0
	if data.Institutions[0].Total != expectedTotal {
		t.Errorf("institution total = %f, want %f", data.Institutions[0].Total, expectedTotal)
	}
}
