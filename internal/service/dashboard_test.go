// Tests for DashboardService — verifies the aggregated dashboard data.
//
// These integration tests check that the dashboard correctly computes:
// - Net worth from multiple accounts
// - Cash vs credit breakdown
// - USD conversion with exchange rates
// - People ledger summary
// - Virtual account integration
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
	"database/sql"
	"fmt"
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
	if data.EGPTotal != 150000 {
		t.Errorf("expected EGPTotal 150000, got %f", data.EGPTotal)
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

	// EGP total = 100000
	if data.EGPTotal != 100000 {
		t.Errorf("EGPTotal = %f, want 100000", data.EGPTotal)
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

// TestDashboardService_GetDashboard_PeopleSummary verifies the per-currency people ledger aggregation.
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

	// Alice: owes me 5000 EGP
	personRepo.Create(context.Background(), models.Person{Name: "Alice", NetBalance: 5000, NetBalanceEGP: 5000})
	// Bob: I owe 3000 EGP
	personRepo.Create(context.Background(), models.Person{Name: "Bob", NetBalance: -3000, NetBalanceEGP: -3000})
	// Carol: owes me 200 USD
	personRepo.Create(context.Background(), models.Person{Name: "Carol", NetBalance: 200, NetBalanceUSD: 200})

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	// Legacy fields: sum across all currencies
	if data.PeopleOwedToMe != 5200 {
		t.Errorf("PeopleOwedToMe = %f, want 5200", data.PeopleOwedToMe)
	}
	if data.PeopleIOwe != -3000 {
		t.Errorf("PeopleIOwe = %f, want -3000", data.PeopleIOwe)
	}

	// Per-currency breakdown
	if len(data.PeopleByCurrency) != 2 {
		t.Fatalf("expected 2 currency summaries, got %d", len(data.PeopleByCurrency))
	}

	// EGP should be first
	egp := data.PeopleByCurrency[0]
	if egp.Currency != "EGP" {
		t.Errorf("expected first currency EGP, got %s", egp.Currency)
	}
	if egp.OwedToMe != 5000 {
		t.Errorf("EGP OwedToMe = %f, want 5000", egp.OwedToMe)
	}
	if egp.IOwe != -3000 {
		t.Errorf("EGP IOwe = %f, want -3000", egp.IOwe)
	}

	// USD second
	usd := data.PeopleByCurrency[1]
	if usd.Currency != "USD" {
		t.Errorf("expected second currency USD, got %s", usd.Currency)
	}
	if usd.OwedToMe != 200 {
		t.Errorf("USD OwedToMe = %f, want 200", usd.OwedToMe)
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

// insertExpense is a test helper that inserts an expense transaction with the given
// currency, amount, date, and optional category name.
func insertExpense(t *testing.T, db *sql.DB, accountID string, currency string, amount float64, date time.Time, categoryName string) {
	t.Helper()
	var categoryID *string
	if categoryName != "" {
		var id string
		err := db.QueryRow(`SELECT id FROM categories WHERE name = $1 LIMIT 1`, categoryName).Scan(&id)
		if err != nil {
			t.Fatalf("finding category %q: %v", categoryName, err)
		}
		categoryID = &id
	}
	_, err := db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, date, category_id)
		VALUES ('expense', $1, $2::currency_type, $3, $4, $5)
	`, amount, currency, accountID, date, categoryID)
	if err != nil {
		t.Fatalf("inserting expense: %v", err)
	}
}

// TestDashboardService_SpendingByCurrency verifies that spending is grouped by currency.
// EGP and USD expenses should appear as separate CurrencySpending entries.
func TestDashboardService_SpendingByCurrency(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)
	svc.SetDB(db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	egpAcc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "EGP Checking",
		Currency: models.CurrencyEGP, InitialBalance: 100000,
	})
	usdAcc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD Savings",
		Currency: models.CurrencyUSD, InitialBalance: 5000,
	})

	now := time.Now()
	thisMonth := time.Date(now.Year(), now.Month(), 5, 0, 0, 0, 0, time.UTC)
	lastMonth := thisMonth.AddDate(0, -1, 0)

	// EGP expenses: this month 3000, last month 2000
	insertExpense(t, db, egpAcc.ID, "EGP", 1500, thisMonth, "Food & Groceries")
	insertExpense(t, db, egpAcc.ID, "EGP", 1000, thisMonth, "Transport")
	insertExpense(t, db, egpAcc.ID, "EGP", 500, thisMonth, "Health")
	insertExpense(t, db, egpAcc.ID, "EGP", 1200, lastMonth, "Food & Groceries")
	insertExpense(t, db, egpAcc.ID, "EGP", 800, lastMonth, "Transport")

	// USD expenses: this month 200, last month 300
	insertExpense(t, db, usdAcc.ID, "USD", 120, thisMonth, "Subscriptions")
	insertExpense(t, db, usdAcc.ID, "USD", 80, thisMonth, "Entertainment")
	insertExpense(t, db, usdAcc.ID, "USD", 200, lastMonth, "Subscriptions")
	insertExpense(t, db, usdAcc.ID, "USD", 100, lastMonth, "Entertainment")

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	// Should have 2 currency entries: EGP first, then USD
	if len(data.SpendingByCurrency) != 2 {
		t.Fatalf("expected 2 currency entries, got %d", len(data.SpendingByCurrency))
	}

	egp := data.SpendingByCurrency[0]
	if egp.Currency != "EGP" {
		t.Errorf("first currency = %s, want EGP", egp.Currency)
	}
	if egp.ThisMonth != 3000 {
		t.Errorf("EGP this month = %f, want 3000", egp.ThisMonth)
	}
	if egp.LastMonth != 2000 {
		t.Errorf("EGP last month = %f, want 2000", egp.LastMonth)
	}
	// Change = (3000 - 2000) / 2000 * 100 = 50%
	expectedChange := 50.0
	if fmt.Sprintf("%.1f", egp.Change) != fmt.Sprintf("%.1f", expectedChange) {
		t.Errorf("EGP change = %.1f%%, want %.1f%%", egp.Change, expectedChange)
	}
	if len(egp.TopCategories) != 3 {
		t.Errorf("EGP top categories = %d, want 3", len(egp.TopCategories))
	}

	usd := data.SpendingByCurrency[1]
	if usd.Currency != "USD" {
		t.Errorf("second currency = %s, want USD", usd.Currency)
	}
	if usd.ThisMonth != 200 {
		t.Errorf("USD this month = %f, want 200", usd.ThisMonth)
	}
	if usd.LastMonth != 300 {
		t.Errorf("USD last month = %f, want 300", usd.LastMonth)
	}
	// Change = (200 - 300) / 300 * 100 = -33.3%
	if usd.Change >= 0 {
		t.Errorf("USD change = %.1f%%, want negative (spending decreased)", usd.Change)
	}

	// Legacy fields should be EGP-only
	if data.ThisMonthSpending != 3000 {
		t.Errorf("legacy ThisMonthSpending = %f, want 3000 (EGP only)", data.ThisMonthSpending)
	}
	if data.LastMonthSpending != 2000 {
		t.Errorf("legacy LastMonthSpending = %f, want 2000 (EGP only)", data.LastMonthSpending)
	}
}

// TestDashboardService_SpendingByCurrency_EGPOnly verifies that when only EGP expenses
// exist, SpendingByCurrency has a single entry and no USD section appears.
func TestDashboardService_SpendingByCurrency_EGPOnly(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)
	svc.SetDB(db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Checking",
		Currency: models.CurrencyEGP, InitialBalance: 50000,
	})

	now := time.Now()
	thisMonth := time.Date(now.Year(), now.Month(), 10, 0, 0, 0, 0, time.UTC)
	insertExpense(t, db, acc.ID, "EGP", 500, thisMonth, "Food & Groceries")

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	if len(data.SpendingByCurrency) != 1 {
		t.Fatalf("expected 1 currency entry, got %d", len(data.SpendingByCurrency))
	}
	if data.SpendingByCurrency[0].Currency != "EGP" {
		t.Errorf("currency = %s, want EGP", data.SpendingByCurrency[0].Currency)
	}
}

// TestDashboardService_SpendingByCurrency_Empty verifies that when there are no
// expenses, SpendingByCurrency is empty and the section won't render.
func TestDashboardService_SpendingByCurrency_Empty(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)
	svc.SetDB(db)

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	if len(data.SpendingByCurrency) != 0 {
		t.Errorf("expected 0 currency entries, got %d", len(data.SpendingByCurrency))
	}
}

// TestDashboardService_SpendingVelocity verifies that the spending pace percentage
// is computed from total spending across all currencies (not EGP-only).
func TestDashboardService_SpendingVelocity(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	instRepo := repository.NewInstitutionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewDashboardService(instRepo, accRepo, txRepo)
	svc.SetDB(db)

	// Set up exchange rate so USD→EGP conversion works
	erRepo := repository.NewExchangeRateRepo(db)
	svc.SetExchangeRateRepo(erRepo)
	_, err := db.Exec(`INSERT INTO exchange_rate_log (date, rate) VALUES (CURRENT_DATE, 50.0)`)
	if err != nil {
		t.Fatalf("inserting exchange rate: %v", err)
	}

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "TestBank"})
	usdAcc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD Account",
		Currency: models.CurrencyUSD, InitialBalance: 5000,
	})

	now := time.Now()
	thisMonth := time.Date(now.Year(), now.Month(), 5, 0, 0, 0, 0, time.UTC)
	lastMonth := thisMonth.AddDate(0, -1, 0)

	// USD only: this month $200, last month $400 → pace = 50%
	insertExpense(t, db, usdAcc.ID, "USD", 200, thisMonth, "Subscriptions")
	insertExpense(t, db, usdAcc.ID, "USD", 400, lastMonth, "Subscriptions")

	data, err := svc.GetDashboard(context.Background())
	if err != nil {
		t.Fatalf("get dashboard: %v", err)
	}

	// Velocity should be ~50% (200/400 * 100), not 0%
	if data.SpendingVelocity.Percentage < 49.0 || data.SpendingVelocity.Percentage > 51.0 {
		t.Errorf("SpendingVelocity.Percentage = %.1f, want ~50.0", data.SpendingVelocity.Percentage)
	}
	if data.SpendingVelocity.DaysTotal == 0 {
		t.Error("SpendingVelocity.DaysTotal should not be 0")
	}
}
