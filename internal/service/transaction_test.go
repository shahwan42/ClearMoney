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
		Type:           models.AccountTypeChecking,
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

func TestTransactionService_Create_Validation(t *testing.T) {
	svc, acc, _ := setupTransactionServiceTest(t)

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
