// Tests for PersonService — verifies lending, borrowing, and repayment logic.
//
// These tests exercise the full loan lifecycle: create person, lend/borrow,
// partial/full repayment, and verify per-currency net balances at each step.
//
// The test pattern follows the TDD workflow this project uses: RED (write failing test),
// GREEN (make it pass), REFACTOR (clean up). Each test method tests one specific behavior.
package service

import (
	"context"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// zeroDT returns the zero value of time.Time — Go's equivalent of null/None for dates.
// When passed to RecordLoan, the service detects it with date.IsZero() and uses time.Now().
// This is a common Go pattern: use the zero value to mean "not specified."
func zeroDT() time.Time { return time.Time{} }

// setupPersonServiceTest creates a clean test environment with a PersonService,
// a userID, an EGP account, and a USD account for multi-currency testing.
func setupPersonServiceTest(t *testing.T) (*PersonService, string, models.Account, models.Account) {
	t.Helper()
	db := testutil.NewTestDB(t)
	userID := testutil.SetupTestUser(t, db)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "persons")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	personRepo := repository.NewPersonRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	svc := NewPersonService(personRepo, txRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB", UserID: userID})
	egpAcc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking EGP",
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
		UserID:         userID,
	})
	usdAcc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings USD",
		Currency:       models.CurrencyUSD,
		InitialBalance: 5000,
		UserID:         userID,
	})

	return svc, userID, egpAcc, usdAcc
}

func TestPersonService_Create(t *testing.T) {
	svc, userID, _, _ := setupPersonServiceTest(t)
	ctx := context.Background()

	p, err := svc.Create(ctx, userID, models.Person{Name: "Ahmed"})
	if err != nil {
		t.Fatalf("create person: %v", err)
	}
	if p.Name != "Ahmed" {
		t.Errorf("expected name Ahmed, got %q", p.Name)
	}
	if p.ID == "" {
		t.Error("expected ID to be set")
	}
	if p.NetBalanceEGP != 0 {
		t.Errorf("expected net_balance_egp 0, got %f", p.NetBalanceEGP)
	}
	if p.NetBalanceUSD != 0 {
		t.Errorf("expected net_balance_usd 0, got %f", p.NetBalanceUSD)
	}
}

func TestPersonService_Create_EmptyName(t *testing.T) {
	svc, userID, _, _ := setupPersonServiceTest(t)
	_, err := svc.Create(context.Background(), userID, models.Person{})
	if err == nil {
		t.Error("expected error for empty name")
	}
}

func TestPersonService_LoanOut(t *testing.T) {
	svc, userID, acc, _ := setupPersonServiceTest(t)
	ctx := context.Background()

	p, _ := svc.Create(ctx, userID, models.Person{Name: "Ali"})

	// Lend 1000 EGP to Ali
	_, err := svc.RecordLoan(ctx, userID, p.ID, acc.ID, 1000, models.CurrencyEGP, models.TransactionTypeLoanOut, nil, zeroDT())
	if err != nil {
		t.Fatalf("record loan: %v", err)
	}

	// Check per-currency balance: EGP should be +1000, USD should be 0
	updated, _ := svc.GetByID(ctx, userID, p.ID)
	if updated.NetBalanceEGP != 1000 {
		t.Errorf("expected net_balance_egp 1000, got %f", updated.NetBalanceEGP)
	}
	if updated.NetBalanceUSD != 0 {
		t.Errorf("expected net_balance_usd 0, got %f", updated.NetBalanceUSD)
	}
}

func TestPersonService_LoanIn(t *testing.T) {
	svc, userID, acc, _ := setupPersonServiceTest(t)
	ctx := context.Background()

	p, _ := svc.Create(ctx, userID, models.Person{Name: "Sara"})

	// Borrow 2000 EGP from Sara
	_, err := svc.RecordLoan(ctx, userID, p.ID, acc.ID, 2000, models.CurrencyEGP, models.TransactionTypeLoanIn, nil, zeroDT())
	if err != nil {
		t.Fatalf("record loan: %v", err)
	}

	// Check per-currency balance: EGP should be -2000
	updated, _ := svc.GetByID(ctx, userID, p.ID)
	if updated.NetBalanceEGP != -2000 {
		t.Errorf("expected net_balance_egp -2000, got %f", updated.NetBalanceEGP)
	}
	if updated.NetBalanceUSD != 0 {
		t.Errorf("expected net_balance_usd 0, got %f", updated.NetBalanceUSD)
	}
}

// TestPersonService_LoanAndRepayment tests the full lifecycle: lend → partial repay → full repay.
// Verifies that per-currency net_balance correctly tracks outstanding debt through multiple operations.
func TestPersonService_LoanAndRepayment(t *testing.T) {
	svc, userID, acc, _ := setupPersonServiceTest(t)
	ctx := context.Background()

	p, _ := svc.Create(ctx, userID, models.Person{Name: "Omar"})

	// Lend 1000 EGP
	svc.RecordLoan(ctx, userID, p.ID, acc.ID, 1000, models.CurrencyEGP, models.TransactionTypeLoanOut, nil, zeroDT())

	// Partial repayment of 500
	_, err := svc.RecordRepayment(ctx, userID, p.ID, acc.ID, 500, models.CurrencyEGP, nil, zeroDT())
	if err != nil {
		t.Fatalf("record repayment: %v", err)
	}

	updated, _ := svc.GetByID(ctx, userID, p.ID)
	if updated.NetBalanceEGP != 500 {
		t.Errorf("expected net_balance_egp 500 after partial repayment, got %f", updated.NetBalanceEGP)
	}

	// Full repayment
	svc.RecordRepayment(ctx, userID, p.ID, acc.ID, 500, models.CurrencyEGP, nil, zeroDT())
	updated, _ = svc.GetByID(ctx, userID, p.ID)
	if updated.NetBalanceEGP != 0 {
		t.Errorf("expected net_balance_egp 0 after full repayment, got %f", updated.NetBalanceEGP)
	}
}

// TestPersonService_MultiCurrency verifies that EGP and USD balances are tracked independently.
func TestPersonService_MultiCurrency(t *testing.T) {
	svc, userID, egpAcc, usdAcc := setupPersonServiceTest(t)
	ctx := context.Background()

	p, _ := svc.Create(ctx, userID, models.Person{Name: "Nadia"})

	// Lend 5000 EGP
	_, err := svc.RecordLoan(ctx, userID, p.ID, egpAcc.ID, 5000, models.CurrencyEGP, models.TransactionTypeLoanOut, nil, zeroDT())
	if err != nil {
		t.Fatalf("EGP loan: %v", err)
	}

	// Borrow 200 USD from the same person
	_, err = svc.RecordLoan(ctx, userID, p.ID, usdAcc.ID, 200, models.CurrencyUSD, models.TransactionTypeLoanIn, nil, zeroDT())
	if err != nil {
		t.Fatalf("USD loan: %v", err)
	}

	updated, _ := svc.GetByID(ctx, userID, p.ID)
	if updated.NetBalanceEGP != 5000 {
		t.Errorf("expected net_balance_egp 5000, got %f", updated.NetBalanceEGP)
	}
	if updated.NetBalanceUSD != -200 {
		t.Errorf("expected net_balance_usd -200, got %f", updated.NetBalanceUSD)
	}
	// Legacy net_balance should be sum of both
	if updated.NetBalance != 4800 {
		t.Errorf("expected legacy net_balance 4800 (5000-200), got %f", updated.NetBalance)
	}
}

// TestPersonService_MultiCurrencyRepayment verifies repayment direction is per-currency.
func TestPersonService_MultiCurrencyRepayment(t *testing.T) {
	svc, userID, egpAcc, usdAcc := setupPersonServiceTest(t)
	ctx := context.Background()

	p, _ := svc.Create(ctx, userID, models.Person{Name: "Karim"})

	// Lend 1000 EGP (they owe me EGP)
	svc.RecordLoan(ctx, userID, p.ID, egpAcc.ID, 1000, models.CurrencyEGP, models.TransactionTypeLoanOut, nil, zeroDT())
	// Borrow 500 USD (I owe them USD)
	svc.RecordLoan(ctx, userID, p.ID, usdAcc.ID, 500, models.CurrencyUSD, models.TransactionTypeLoanIn, nil, zeroDT())

	// Repay 300 USD — should reduce my USD debt (direction: I owe them → money leaves my account)
	_, err := svc.RecordRepayment(ctx, userID, p.ID, usdAcc.ID, 300, models.CurrencyUSD, nil, zeroDT())
	if err != nil {
		t.Fatalf("USD repayment: %v", err)
	}

	updated, _ := svc.GetByID(ctx, userID, p.ID)
	if updated.NetBalanceEGP != 1000 {
		t.Errorf("EGP balance should be unchanged at 1000, got %f", updated.NetBalanceEGP)
	}
	if updated.NetBalanceUSD != -200 {
		t.Errorf("expected net_balance_usd -200 after repaying 300, got %f", updated.NetBalanceUSD)
	}
}

// TestPersonService_DebtSummaryByCurrency verifies per-currency grouping in debt summary.
func TestPersonService_DebtSummaryByCurrency(t *testing.T) {
	svc, userID, egpAcc, usdAcc := setupPersonServiceTest(t)
	ctx := context.Background()

	p, _ := svc.Create(ctx, userID, models.Person{Name: "Layla"})

	// EGP: lend 2000
	svc.RecordLoan(ctx, userID, p.ID, egpAcc.ID, 2000, models.CurrencyEGP, models.TransactionTypeLoanOut, nil, zeroDT())
	// USD: lend 100
	svc.RecordLoan(ctx, userID, p.ID, usdAcc.ID, 100, models.CurrencyUSD, models.TransactionTypeLoanOut, nil, zeroDT())
	// EGP: repay 500
	svc.RecordRepayment(ctx, userID, p.ID, egpAcc.ID, 500, models.CurrencyEGP, nil, zeroDT())

	summary, err := svc.GetDebtSummary(ctx, userID, p.ID)
	if err != nil {
		t.Fatalf("debt summary: %v", err)
	}

	if len(summary.ByCurrency) != 2 {
		t.Fatalf("expected 2 currency breakdowns, got %d", len(summary.ByCurrency))
	}

	// EGP should be first (ordered EGP, then USD)
	egp := summary.ByCurrency[0]
	if egp.Currency != models.CurrencyEGP {
		t.Errorf("expected first currency EGP, got %s", egp.Currency)
	}
	if egp.TotalLent != 2000 {
		t.Errorf("expected EGP total lent 2000, got %f", egp.TotalLent)
	}
	if egp.TotalRepaid != 500 {
		t.Errorf("expected EGP total repaid 500, got %f", egp.TotalRepaid)
	}

	usd := summary.ByCurrency[1]
	if usd.Currency != models.CurrencyUSD {
		t.Errorf("expected second currency USD, got %s", usd.Currency)
	}
	if usd.TotalLent != 100 {
		t.Errorf("expected USD total lent 100, got %f", usd.TotalLent)
	}
}

func TestPersonService_GetAll(t *testing.T) {
	svc, userID, _, _ := setupPersonServiceTest(t)
	ctx := context.Background()

	svc.Create(ctx, userID, models.Person{Name: "Zara"})
	svc.Create(ctx, userID, models.Person{Name: "Ahmed"})

	all, err := svc.GetAll(ctx, userID)
	if err != nil {
		t.Fatalf("get all: %v", err)
	}
	if len(all) != 2 {
		t.Fatalf("expected 2 persons, got %d", len(all))
	}
	// Should be sorted by name
	if all[0].Name != "Ahmed" {
		t.Errorf("expected first person to be Ahmed (alphabetical), got %q", all[0].Name)
	}
}
