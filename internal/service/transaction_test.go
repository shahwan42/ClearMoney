// Tests for TransactionService — the most comprehensively tested service.
//
// These are INTEGRATION tests that exercise the full stack: service → repository → PostgreSQL.
// They verify atomic balance updates, transfer/exchange linking, credit card limits, and more.
//
// Go testing patterns used here:
//
// 1. Setup helpers: setupTransactionServiceTest() creates a clean database state with
//    institutions, accounts, and categories. Marked with t.Helper() so test failures
//    report the caller's line, not the helper's. Like PHPUnit's setUp() or Django's setUp().
//
// 2. Table-driven tests: TestTransactionService_Create_Validation uses a slice of test cases
//    with t.Run() for named sub-tests. This is Go's recommended pattern for testing multiple
//    inputs against the same logic. Like PHPUnit's @dataProvider or Django's subTest().
//    See: https://go.dev/wiki/TableDrivenTests
//
// 3. t.Fatalf vs t.Errorf: Fatalf stops the test immediately (like PHPUnit's $this->fail()).
//    Errorf records the failure but continues (like $this->addFailure() — test keeps running).
//    Use Fatalf for setup failures, Errorf for assertion failures.
//
// 4. context.Background(): In tests, we use the "empty" context since there's no HTTP
//    request to derive cancellation from. In production, the handler passes the request's context.
package service

import (
	"context"
	"testing"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

// setupTransactionServiceTest creates a clean environment with a transaction service,
// an account, and an expense category for testing.
//
// Returns (service, account, categoryID) — a Go idiom for returning multiple values from helpers.
// The t.Helper() call marks this as a helper so stack traces skip to the calling test.
func setupTransactionServiceTest(t *testing.T) (*TransactionService, models.Account, string) {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Test Bank"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeCurrent,
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
	})
	catID := testutil.GetFirstCategoryID(t, db, models.CategoryTypeExpense)

	return svc, acc, catID
}

func TestTransactionService_Create_Expense(t *testing.T) {
	svc, acc, catID := setupTransactionServiceTest(t)

	created, newBalance, err := svc.Create(context.Background(), models.Transaction{
		Type:       models.TransactionTypeExpense,
		Amount:     3000,
		Currency:   models.CurrencyEGP,
		AccountID:  acc.ID,
		CategoryID: &catID,
	})
	if err != nil {
		t.Fatalf("create expense: %v", err)
	}
	if created.ID == "" {
		t.Error("expected ID")
	}
	// Balance should decrease: 10000 - 3000 = 7000
	if newBalance != 7000 {
		t.Errorf("expected balance 7000, got %f", newBalance)
	}
}

func TestTransactionService_Create_Income(t *testing.T) {
	svc, acc, _ := setupTransactionServiceTest(t)
	catID := testutil.GetFirstCategoryID(t, testutil.NewTestDB(t), models.CategoryTypeIncome)

	created, newBalance, err := svc.Create(context.Background(), models.Transaction{
		Type:       models.TransactionTypeIncome,
		Amount:     5000,
		Currency:   models.CurrencyEGP,
		AccountID:  acc.ID,
		CategoryID: &catID,
	})
	if err != nil {
		t.Fatalf("create income: %v", err)
	}
	if created.ID == "" {
		t.Error("expected ID")
	}
	// Balance should increase: 10000 + 5000 = 15000
	if newBalance != 15000 {
		t.Errorf("expected balance 15000, got %f", newBalance)
	}
}

// TestTransactionService_Create_Validation uses TABLE-DRIVEN TESTS — the most important
// Go testing pattern. Each test case is a struct in a slice, run via t.Run() for named sub-tests.
//
// This pattern is like PHPUnit's @dataProvider:
//   /** @dataProvider validationCases */
//   public function test_create_validation($name, $tx) { ... }
//
// Or Django's subTest:
//   for name, tx in cases: with self.subTest(name=name): ...
//
// Benefits: each sub-test runs independently, has its own name, and can be run in isolation:
//   go test -run TestTransactionService_Create_Validation/zero_amount
func TestTransactionService_Create_Validation(t *testing.T) {
	svc, acc, _ := setupTransactionServiceTest(t)

	// Anonymous struct: Go lets you define struct types inline for one-off use.
	// Each element has a test name and a Transaction with intentionally invalid data.
	tests := []struct {
		name string
		tx   models.Transaction
	}{
		{"zero amount", models.Transaction{Amount: 0, AccountID: acc.ID, Type: "expense", Currency: "EGP"}},
		{"negative amount", models.Transaction{Amount: -100, AccountID: acc.ID, Type: "expense", Currency: "EGP"}},
		{"missing account_id", models.Transaction{Amount: 100, Type: "expense", Currency: "EGP"}},
		{"missing type", models.Transaction{Amount: 100, AccountID: acc.ID, Currency: "EGP"}},
		{"missing currency", models.Transaction{Amount: 100, AccountID: acc.ID, Type: "expense"}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, _, err := svc.Create(context.Background(), tt.tx)
			if err == nil {
				t.Errorf("expected validation error for %s", tt.name)
			}
		})
	}
}

func TestTransactionService_Delete_ReversesBalance(t *testing.T) {
	svc, acc, _ := setupTransactionServiceTest(t)

	// Create an expense that decreases balance by 2000
	created, _, err := svc.Create(context.Background(), models.Transaction{
		Type:      models.TransactionTypeExpense,
		Amount:    2000,
		Currency:  models.CurrencyEGP,
		AccountID: acc.ID,
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}

	// Delete it — balance should be restored to 10000
	if err := svc.Delete(context.Background(), created.ID); err != nil {
		t.Fatalf("delete: %v", err)
	}

	// Verify balance is restored
	_, newBalance, err := svc.Create(context.Background(), models.Transaction{
		Type:      models.TransactionTypeExpense,
		Amount:    0.01, // tiny transaction just to check balance
		Currency:  models.CurrencyEGP,
		AccountID: acc.ID,
	})
	if err != nil {
		t.Fatalf("check balance: %v", err)
	}
	// 10000 (restored) - 0.01 = 9999.99
	expected := 9999.99
	if newBalance != expected {
		t.Errorf("expected balance %f after reversal, got %f", expected, newBalance)
	}
}

func TestTransactionService_GetRecent(t *testing.T) {
	svc, acc, _ := setupTransactionServiceTest(t)

	for i := 0; i < 3; i++ {
		svc.Create(context.Background(), models.Transaction{
			Type:      models.TransactionTypeExpense,
			Amount:    float64(100 * (i + 1)),
			Currency:  models.CurrencyEGP,
			AccountID: acc.ID,
		})
	}

	txns, err := svc.GetRecent(context.Background(), 2)
	if err != nil {
		t.Fatalf("get recent: %v", err)
	}
	if len(txns) != 2 {
		t.Errorf("expected 2, got %d", len(txns))
	}
}

func TestTransactionService_GetRecent_DefaultLimit(t *testing.T) {
	svc, _, _ := setupTransactionServiceTest(t)

	// Passing 0 should default to 15
	txns, err := svc.GetRecent(context.Background(), 0)
	if err != nil {
		t.Fatalf("get recent: %v", err)
	}
	// Just verify it doesn't error — we don't have 15 transactions
	_ = txns
}

func TestTransactionService_GetByAccount(t *testing.T) {
	svc, acc, _ := setupTransactionServiceTest(t)

	svc.Create(context.Background(), models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 100,
		Currency: models.CurrencyEGP, AccountID: acc.ID,
	})

	txns, err := svc.GetByAccount(context.Background(), acc.ID, 10)
	if err != nil {
		t.Fatalf("get by account: %v", err)
	}
	if len(txns) != 1 {
		t.Errorf("expected 1, got %d", len(txns))
	}
}

func TestTransactionService_CreateTransfer(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	src := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Checking", Currency: models.CurrencyEGP, InitialBalance: 10000,
	})
	dst := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Savings", Type: models.AccountTypeSavings, Currency: models.CurrencyEGP, InitialBalance: 5000,
	})

	debit, credit, err := svc.CreateTransfer(context.Background(), src.ID, dst.ID, 3000, models.CurrencyEGP, nil, time.Time{})
	if err != nil {
		t.Fatalf("create transfer: %v", err)
	}

	// Both should be transfer type
	if debit.Type != models.TransactionTypeTransfer || credit.Type != models.TransactionTypeTransfer {
		t.Error("expected both legs to be transfer type")
	}

	// They should be linked
	if debit.LinkedTransactionID == nil || credit.LinkedTransactionID == nil {
		t.Fatal("expected linked transaction IDs")
	}

	// Verify balances: src = 10000 - 3000 = 7000, dst = 5000 + 3000 = 8000
	srcAcc, _ := accRepo.GetByID(context.Background(), src.ID)
	dstAcc, _ := accRepo.GetByID(context.Background(), dst.ID)

	if srcAcc.CurrentBalance != 7000 {
		t.Errorf("source balance: expected 7000, got %f", srcAcc.CurrentBalance)
	}
	if dstAcc.CurrentBalance != 8000 {
		t.Errorf("dest balance: expected 8000, got %f", dstAcc.CurrentBalance)
	}
}

func TestTransactionService_CreateTransfer_SameAccount(t *testing.T) {
	svc, acc, _ := setupTransactionServiceTest(t)

	_, _, err := svc.CreateTransfer(context.Background(), acc.ID, acc.ID, 1000, models.CurrencyEGP, nil, time.Time{})
	if err == nil {
		t.Error("expected error for same-account transfer")
	}
}

func TestTransactionService_CreateTransfer_CrossCurrency(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	egp := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "EGP", Currency: models.CurrencyEGP, InitialBalance: 10000,
	})
	usd := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD", Currency: models.CurrencyUSD, InitialBalance: 5000,
	})

	_, _, err := svc.CreateTransfer(context.Background(), egp.ID, usd.ID, 1000, models.CurrencyEGP, nil, time.Time{})
	if err == nil {
		t.Error("expected error for cross-currency transfer")
	}
}

func TestTransactionService_DeleteTransfer_ReversesBothBalances(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	src := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Checking", Currency: models.CurrencyEGP, InitialBalance: 10000,
	})
	dst := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Savings", Type: models.AccountTypeSavings, Currency: models.CurrencyEGP, InitialBalance: 5000,
	})

	debit, _, err := svc.CreateTransfer(context.Background(), src.ID, dst.ID, 3000, models.CurrencyEGP, nil, time.Time{})
	if err != nil {
		t.Fatalf("create: %v", err)
	}

	// Delete the debit leg — should also delete credit and reverse both
	if err := svc.Delete(context.Background(), debit.ID); err != nil {
		t.Fatalf("delete: %v", err)
	}

	// Balances should be restored
	srcAcc, _ := accRepo.GetByID(context.Background(), src.ID)
	dstAcc, _ := accRepo.GetByID(context.Background(), dst.ID)

	if srcAcc.CurrentBalance != 10000 {
		t.Errorf("source: expected 10000, got %f", srcAcc.CurrentBalance)
	}
	if dstAcc.CurrentBalance != 5000 {
		t.Errorf("dest: expected 5000, got %f", dstAcc.CurrentBalance)
	}
}

func TestTransactionService_CreditCard_ExpenseMakesNegative(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	creditLimit := 500000.0
	cc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Credit Card",
		Type:           models.AccountTypeCreditCard,
		Currency:       models.CurrencyEGP,
		InitialBalance: 0,
		CreditLimit:    &creditLimit,
	})

	// Expense on credit card: balance should go negative
	_, newBalance, err := svc.Create(context.Background(), models.Transaction{
		Type:      models.TransactionTypeExpense,
		Amount:    50000,
		Currency:  models.CurrencyEGP,
		AccountID: cc.ID,
	})
	if err != nil {
		t.Fatalf("expense: %v", err)
	}
	if newBalance != -50000 {
		t.Errorf("expected -50000, got %f", newBalance)
	}
}

func TestTransactionService_CreditCard_PaymentRestoresBalance(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	creditLimit := 500000.0
	cc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Credit Card",
		Type:           models.AccountTypeCreditCard,
		Currency:       models.CurrencyEGP,
		InitialBalance: 0,
		CreditLimit:    &creditLimit,
	})

	// Expense: 0 → -100000
	svc.Create(context.Background(), models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 100000,
		Currency: models.CurrencyEGP, AccountID: cc.ID,
	})

	// Payment (income): -100000 → -70000
	_, newBalance, err := svc.Create(context.Background(), models.Transaction{
		Type:      models.TransactionTypeIncome,
		Amount:    30000,
		Currency:  models.CurrencyEGP,
		AccountID: cc.ID,
	})
	if err != nil {
		t.Fatalf("payment: %v", err)
	}
	if newBalance != -70000 {
		t.Errorf("expected -70000, got %f", newBalance)
	}
}

func TestTransactionService_CreditCard_ExceedLimit(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	creditLimit := 10000.0
	cc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Credit Card",
		Type:           models.AccountTypeCreditCard,
		Currency:       models.CurrencyEGP,
		InitialBalance: 0,
		CreditLimit:    &creditLimit,
	})

	// Try to exceed the 10000 limit
	_, _, err := svc.Create(context.Background(), models.Transaction{
		Type:      models.TransactionTypeExpense,
		Amount:    15000,
		Currency:  models.CurrencyEGP,
		AccountID: cc.ID,
	})
	if err == nil {
		t.Error("expected error for exceeding credit limit")
	}
}

func TestTransactionService_CreateExchange(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	rateRepo := repository.NewExchangeRateRepo(db)
	svc := NewTransactionService(txRepo, accRepo)
	svc.SetExchangeRateRepo(rateRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	usd := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD Account", Currency: models.CurrencyUSD, InitialBalance: 5000,
	})
	egp := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "EGP Account", Currency: models.CurrencyEGP, InitialBalance: 100000,
	})

	// Exchange 1000 USD at rate 50.5 → 50500 EGP
	amount := 1000.0
	rate := 50.5
	debit, credit, err := svc.CreateExchange(context.Background(), ExchangeParams{
		SourceAccountID: usd.ID,
		DestAccountID:   egp.ID,
		Amount:          &amount,
		Rate:            &rate,
	})
	if err != nil {
		t.Fatalf("create exchange: %v", err)
	}

	if debit.Type != models.TransactionTypeExchange {
		t.Error("expected exchange type")
	}
	if debit.Amount != 1000 {
		t.Errorf("debit amount: expected 1000, got %f", debit.Amount)
	}
	if credit.Amount != 50500 {
		t.Errorf("credit amount: expected 50500, got %f", credit.Amount)
	}

	// Verify balances
	usdAcc, _ := accRepo.GetByID(context.Background(), usd.ID)
	egpAcc, _ := accRepo.GetByID(context.Background(), egp.ID)

	if usdAcc.CurrentBalance != 4000 {
		t.Errorf("USD balance: expected 4000, got %f", usdAcc.CurrentBalance)
	}
	if egpAcc.CurrentBalance != 150500 {
		t.Errorf("EGP balance: expected 150500, got %f", egpAcc.CurrentBalance)
	}
}

func TestTransactionService_CreateExchange_AutoCalcRate(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	usd := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD", Currency: models.CurrencyUSD, InitialBalance: 5000,
	})
	egp := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "EGP", Currency: models.CurrencyEGP, InitialBalance: 100000,
	})

	// Provide amount + counter_amount, rate should be auto-calculated
	amount := 100.0
	counterAmount := 5050.0
	_, _, err := svc.CreateExchange(context.Background(), ExchangeParams{
		SourceAccountID: usd.ID,
		DestAccountID:   egp.ID,
		Amount:          &amount,
		CounterAmount:   &counterAmount,
	})
	if err != nil {
		t.Fatalf("create exchange: %v", err)
	}

	// Rate should be 5050/100 = 50.5
	usdAcc, _ := accRepo.GetByID(context.Background(), usd.ID)
	if usdAcc.CurrentBalance != 4900 {
		t.Errorf("expected 4900, got %f", usdAcc.CurrentBalance)
	}
}

func TestTransactionService_CreateExchange_SameCurrency(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	acc1 := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "A1", Currency: models.CurrencyEGP, InitialBalance: 1000,
	})
	acc2 := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "A2", Currency: models.CurrencyEGP, InitialBalance: 1000,
	})

	amount := 100.0
	rate := 1.0
	_, _, err := svc.CreateExchange(context.Background(), ExchangeParams{
		SourceAccountID: acc1.ID,
		DestAccountID:   acc2.ID,
		Amount:          &amount,
		Rate:            &rate,
	})
	if err == nil {
		t.Error("expected error for same-currency exchange")
	}
}

// TestTransactionService_CreateExchange_EGPtoUSD verifies that exchanging EGP→USD
// correctly handles the rate direction. Rate=50 means "1 USD = 50 EGP", so
// 5000 EGP at rate 50 should yield 100 USD (5000/50), not 250000.
func TestTransactionService_CreateExchange_EGPtoUSD(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	testutil.CleanTable(t, db, "exchange_rate_log")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	rateRepo := repository.NewExchangeRateRepo(db)
	svc := NewTransactionService(txRepo, accRepo)
	svc.SetExchangeRateRepo(rateRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Bank"})
	egp := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "EGP Account", Currency: models.CurrencyEGP, InitialBalance: 100000,
	})
	usd := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD Account", Currency: models.CurrencyUSD, InitialBalance: 2000,
	})

	// Exchange 5000 EGP at rate 50 (1 USD = 50 EGP) → should yield 100 USD
	amount := 5000.0
	rate := 50.0
	debit, credit, err := svc.CreateExchange(context.Background(), ExchangeParams{
		SourceAccountID: egp.ID,
		DestAccountID:   usd.ID,
		Amount:          &amount,
		Rate:            &rate,
	})
	if err != nil {
		t.Fatalf("create exchange: %v", err)
	}

	// Debit leg: 5000 EGP out
	if debit.Amount != 5000 {
		t.Errorf("debit amount: expected 5000, got %f", debit.Amount)
	}
	// Credit leg: 100 USD in (5000 / 50)
	if credit.Amount != 100 {
		t.Errorf("credit amount: expected 100, got %f", credit.Amount)
	}

	// ExchangeRate on both legs should be the display rate (50 = EGP per USD)
	if debit.ExchangeRate == nil || *debit.ExchangeRate != 50 {
		t.Errorf("debit exchange rate: expected 50, got %v", debit.ExchangeRate)
	}

	// Verify balances
	egpAcc, _ := accRepo.GetByID(context.Background(), egp.ID)
	usdAcc, _ := accRepo.GetByID(context.Background(), usd.ID)
	if egpAcc.CurrentBalance != 95000 {
		t.Errorf("EGP balance: expected 95000, got %f", egpAcc.CurrentBalance)
	}
	if usdAcc.CurrentBalance != 2100 {
		t.Errorf("USD balance: expected 2100, got %f", usdAcc.CurrentBalance)
	}

	// Verify exchange rate logged as EGP per USD (50), not inverted (0.02)
	rates, err := rateRepo.GetAll(context.Background())
	if err != nil {
		t.Fatalf("get rates: %v", err)
	}
	if len(rates) == 0 {
		t.Fatal("expected at least one logged rate")
	}
	if rates[0].Rate != 50 {
		t.Errorf("logged rate: expected 50, got %f", rates[0].Rate)
	}
}

// TestTransactionService_CreateExchange_EGPtoUSD_AutoCalc verifies auto-calc
// when only amount + counter_amount are provided for EGP→USD.
func TestTransactionService_CreateExchange_EGPtoUSD_AutoCalc(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	testutil.CleanTable(t, db, "exchange_rate_log")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	rateRepo := repository.NewExchangeRateRepo(db)
	svc := NewTransactionService(txRepo, accRepo)
	svc.SetExchangeRateRepo(rateRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Bank"})
	egp := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "EGP", Currency: models.CurrencyEGP, InitialBalance: 100000,
	})
	usd := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "USD", Currency: models.CurrencyUSD, InitialBalance: 2000,
	})

	// Provide amount (EGP) + counter_amount (USD), rate should be auto-logged as 50
	amount := 5000.0
	counter := 100.0
	_, _, err := svc.CreateExchange(context.Background(), ExchangeParams{
		SourceAccountID: egp.ID,
		DestAccountID:   usd.ID,
		Amount:          &amount,
		CounterAmount:   &counter,
	})
	if err != nil {
		t.Fatalf("create exchange: %v", err)
	}

	// Rate logged should be 50 (EGP per USD = 5000/100)
	rates, _ := rateRepo.GetAll(context.Background())
	if len(rates) == 0 {
		t.Fatal("expected logged rate")
	}
	if rates[0].Rate != 50 {
		t.Errorf("logged rate: expected 50, got %f", rates[0].Rate)
	}
}

// TestCalculateInstapayFee is a pure-function unit test — no database, no setup.
// Table-driven test pattern with expected outputs for each input.
// This is the simplest kind of Go test: deterministic, fast, no side effects.
func TestCalculateInstapayFee(t *testing.T) {
	tests := []struct {
		amount   float64
		expected float64
	}{
		{100, 0.5},       // 0.1% = 0.1, below minimum → 0.5
		{500, 0.5},       // 0.1% = 0.5, at minimum → 0.5
		{10000, 10},      // 0.1% = 10
		{20000, 20},      // 0.1% = 20, at maximum
		{50000, 20},      // 0.1% = 50, above maximum → 20
		{1000, 1},        // 0.1% = 1
	}
	for _, tt := range tests {
		got := CalculateInstapayFee(tt.amount)
		if got != tt.expected {
			t.Errorf("CalculateInstapayFee(%v) = %v, want %v", tt.amount, got, tt.expected)
		}
	}
}

func TestTransactionService_CreateInstapayTransfer(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	src := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Source", Currency: models.CurrencyEGP, InitialBalance: 50000,
	})
	dest := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Dest", Currency: models.CurrencyEGP, InitialBalance: 10000,
	})

	feesCatID := testutil.GetFirstCategoryID(t, db, models.CategoryTypeExpense)

	_, _, fee, err := svc.CreateInstapayTransfer(
		context.Background(), src.ID, dest.ID, 10000, models.CurrencyEGP, nil, time.Now(), feesCatID,
	)
	if err != nil {
		t.Fatalf("instapay transfer: %v", err)
	}
	if fee != 10 {
		t.Errorf("expected fee 10, got %f", fee)
	}

	// Source balance: 50000 - 10000 (transfer) - 10 (fee) = 39990
	srcAcc, _ := accRepo.GetByID(context.Background(), src.ID)
	if srcAcc.CurrentBalance != 39990 {
		t.Errorf("expected source balance 39990, got %f", srcAcc.CurrentBalance)
	}

	// Dest balance: 10000 + 10000 = 20000
	destAcc, _ := accRepo.GetByID(context.Background(), dest.ID)
	if destAcc.CurrentBalance != 20000 {
		t.Errorf("expected dest balance 20000, got %f", destAcc.CurrentBalance)
	}
}

func TestTransactionService_SmartDefaults_LastAccount(t *testing.T) {
	svc, acc, catID := setupTransactionServiceTest(t)
	ctx := context.Background()

	// No history: defaults should be empty
	defaults := svc.GetSmartDefaults(ctx, "expense")
	if defaults.LastAccountID != "" {
		t.Errorf("expected empty last account, got %q", defaults.LastAccountID)
	}

	// Create a transaction
	svc.Create(ctx, models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 100,
		Currency: models.CurrencyEGP, AccountID: acc.ID, CategoryID: &catID,
	})

	defaults = svc.GetSmartDefaults(ctx, "expense")
	if defaults.LastAccountID != acc.ID {
		t.Errorf("expected last account %q, got %q", acc.ID, defaults.LastAccountID)
	}
}

func TestTransactionService_SmartDefaults_AutoCategory(t *testing.T) {
	svc, acc, catID := setupTransactionServiceTest(t)
	ctx := context.Background()

	// Create 2 transactions with same category — not enough for auto-select
	for i := 0; i < 2; i++ {
		svc.Create(ctx, models.Transaction{
			Type: models.TransactionTypeExpense, Amount: 50,
			Currency: models.CurrencyEGP, AccountID: acc.ID, CategoryID: &catID,
		})
	}
	defaults := svc.GetSmartDefaults(ctx, "expense")
	if defaults.AutoCategoryID != "" {
		t.Error("expected no auto-category with only 2 consecutive uses")
	}

	// Third consecutive use — should trigger auto-select
	svc.Create(ctx, models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 50,
		Currency: models.CurrencyEGP, AccountID: acc.ID, CategoryID: &catID,
	})
	defaults = svc.GetSmartDefaults(ctx, "expense")
	if defaults.AutoCategoryID != catID {
		t.Errorf("expected auto-category %q after 3 uses, got %q", catID, defaults.AutoCategoryID)
	}
}

func TestTransactionService_FawryCashout(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC"})
	creditLimit := 100000.0
	cc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Credit Card", Type: models.AccountTypeCreditCard,
		Currency: models.CurrencyEGP, InitialBalance: 0, CreditLimit: &creditLimit,
	})
	prepaid := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Fawry Prepaid", Type: models.AccountTypePrepaid,
		Currency: models.CurrencyEGP, InitialBalance: 0,
	})

	charge, credit, err := svc.CreateFawryCashout(
		context.Background(), cc.ID, prepaid.ID,
		5000, 50, models.CurrencyEGP, nil, time.Now(), "",
	)
	if err != nil {
		t.Fatalf("fawry cashout: %v", err)
	}

	// Charge should be expense for total (amount + fee)
	if charge.Type != models.TransactionTypeExpense {
		t.Errorf("charge type = %s, want expense", charge.Type)
	}
	if charge.Amount != 5050 {
		t.Errorf("charge amount = %f, want 5050", charge.Amount)
	}

	// Credit should be income for net amount
	if credit.Type != models.TransactionTypeIncome {
		t.Errorf("credit type = %s, want income", credit.Type)
	}
	if credit.Amount != 5000 {
		t.Errorf("credit amount = %f, want 5000", credit.Amount)
	}

	// Credit card: 0 - 5050 = -5050
	ccAcc, _ := accRepo.GetByID(context.Background(), cc.ID)
	if ccAcc.CurrentBalance != -5050 {
		t.Errorf("cc balance = %f, want -5050", ccAcc.CurrentBalance)
	}

	// Prepaid: 0 + 5000 = 5000
	prepaidAcc, _ := accRepo.GetByID(context.Background(), prepaid.ID)
	if prepaidAcc.CurrentBalance != 5000 {
		t.Errorf("prepaid balance = %f, want 5000", prepaidAcc.CurrentBalance)
	}

	// Linked
	if charge.LinkedTransactionID == nil || *charge.LinkedTransactionID != credit.ID {
		t.Error("charge should be linked to credit")
	}
}

func TestTransactionService_FawryCashout_ValidationErrors(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewTransactionService(txRepo, accRepo)

	tests := []struct {
		name      string
		ccID      string
		prepaidID string
		amount    float64
		fee       float64
	}{
		{"zero amount", "a", "b", 0, 10},
		{"negative fee", "a", "b", 1000, -5},
		{"missing cc", "", "b", 1000, 10},
		{"same account", "a", "a", 1000, 10},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, _, err := svc.CreateFawryCashout(
				context.Background(), tt.ccID, tt.prepaidID,
				tt.amount, tt.fee, models.CurrencyEGP, nil, time.Now(), "",
			)
			if err == nil {
				t.Errorf("expected error for %s", tt.name)
			}
		})
	}
}

func TestTransactionService_SmartDefaults_RecentCategories(t *testing.T) {
	svc, acc, catID := setupTransactionServiceTest(t)
	ctx := context.Background()

	// Create a few transactions
	svc.Create(ctx, models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 100,
		Currency: models.CurrencyEGP, AccountID: acc.ID, CategoryID: &catID,
	})

	defaults := svc.GetSmartDefaults(ctx, "expense")
	if len(defaults.RecentCategoryIDs) == 0 {
		t.Error("expected at least 1 recent category")
	}
	if defaults.RecentCategoryIDs[0] != catID {
		t.Errorf("expected first recent category to be %q, got %q", catID, defaults.RecentCategoryIDs[0])
	}
}
