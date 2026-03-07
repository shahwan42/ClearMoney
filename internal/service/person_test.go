package service

import (
	"context"
	"testing"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func zeroDT() time.Time { return time.Time{} }

func setupPersonServiceTest(t *testing.T) (*PersonService, models.Account) {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "persons")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	personRepo := repository.NewPersonRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewPersonService(personRepo, txRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})

	_ = accRepo // keep import
	return svc, acc
}

func TestPersonService_Create(t *testing.T) {
	svc, _ := setupPersonServiceTest(t)
	ctx := context.Background()

	p, err := svc.Create(ctx, models.Person{Name: "Ahmed"})
	if err != nil {
		t.Fatalf("create person: %v", err)
	}
	if p.Name != "Ahmed" {
		t.Errorf("expected name Ahmed, got %q", p.Name)
	}
	if p.ID == "" {
		t.Error("expected ID to be set")
	}
	if p.NetBalance != 0 {
		t.Errorf("expected net_balance 0, got %f", p.NetBalance)
	}
}

func TestPersonService_Create_EmptyName(t *testing.T) {
	svc, _ := setupPersonServiceTest(t)
	_, err := svc.Create(context.Background(), models.Person{})
	if err == nil {
		t.Error("expected error for empty name")
	}
}

func TestPersonService_LoanOut(t *testing.T) {
	svc, acc := setupPersonServiceTest(t)
	ctx := context.Background()

	p, _ := svc.Create(ctx, models.Person{Name: "Ali"})

	// Lend 1000 to Ali
	_, err := svc.RecordLoan(ctx, p.ID, acc.ID, 1000, models.CurrencyEGP, models.TransactionTypeLoanOut, nil, zeroDT())
	if err != nil {
		t.Fatalf("record loan: %v", err)
	}

	// Check person balance: should be +1000 (they owe me)
	updated, _ := svc.GetByID(ctx, p.ID)
	if updated.NetBalance != 1000 {
		t.Errorf("expected net_balance 1000, got %f", updated.NetBalance)
	}
}

func TestPersonService_LoanIn(t *testing.T) {
	svc, acc := setupPersonServiceTest(t)
	ctx := context.Background()

	p, _ := svc.Create(ctx, models.Person{Name: "Sara"})

	// Borrow 2000 from Sara
	_, err := svc.RecordLoan(ctx, p.ID, acc.ID, 2000, models.CurrencyEGP, models.TransactionTypeLoanIn, nil, zeroDT())
	if err != nil {
		t.Fatalf("record loan: %v", err)
	}

	// Check person balance: should be -2000 (I owe them)
	updated, _ := svc.GetByID(ctx, p.ID)
	if updated.NetBalance != -2000 {
		t.Errorf("expected net_balance -2000, got %f", updated.NetBalance)
	}
}

func TestPersonService_LoanAndRepayment(t *testing.T) {
	svc, acc := setupPersonServiceTest(t)
	ctx := context.Background()

	p, _ := svc.Create(ctx, models.Person{Name: "Omar"})

	// Lend 1000
	svc.RecordLoan(ctx, p.ID, acc.ID, 1000, models.CurrencyEGP, models.TransactionTypeLoanOut, nil, zeroDT())

	// Partial repayment of 500
	_, err := svc.RecordRepayment(ctx, p.ID, acc.ID, 500, models.CurrencyEGP, nil, zeroDT())
	if err != nil {
		t.Fatalf("record repayment: %v", err)
	}

	updated, _ := svc.GetByID(ctx, p.ID)
	if updated.NetBalance != 500 {
		t.Errorf("expected net_balance 500 after partial repayment, got %f", updated.NetBalance)
	}

	// Full repayment
	svc.RecordRepayment(ctx, p.ID, acc.ID, 500, models.CurrencyEGP, nil, zeroDT())
	updated, _ = svc.GetByID(ctx, p.ID)
	if updated.NetBalance != 0 {
		t.Errorf("expected net_balance 0 after full repayment, got %f", updated.NetBalance)
	}
}

func TestPersonService_GetAll(t *testing.T) {
	svc, _ := setupPersonServiceTest(t)
	ctx := context.Background()

	svc.Create(ctx, models.Person{Name: "Zara"})
	svc.Create(ctx, models.Person{Name: "Ahmed"})

	all, err := svc.GetAll(ctx)
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
