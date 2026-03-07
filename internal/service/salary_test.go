package service

import (
	"context"
	"testing"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

// setupSalaryTest creates a SalaryService with USD and EGP accounts.
func setupSalaryTest(t *testing.T) (*SalaryService, models.Account, models.Account) {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	svc := NewSalaryService(txRepo, accRepo)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})
	usdAcc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "USD Savings",
		Currency:       models.CurrencyUSD,
		InitialBalance: 0,
	})
	egpAcc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "EGP Main",
		Currency:       models.CurrencyEGP,
		InitialBalance: 0,
	})

	return svc, usdAcc, egpAcc
}

func TestSalaryService_DistributeSalary_Basic(t *testing.T) {
	svc, usdAcc, egpAcc := setupSalaryTest(t)

	dist := SalaryDistribution{
		SalaryUSD:    1000,
		ExchangeRate: 50,
		USDAccountID: usdAcc.ID,
		EGPAccountID: egpAcc.ID,
		Date:         time.Now(),
	}

	err := svc.DistributeSalary(context.Background(), dist)
	if err != nil {
		t.Fatalf("DistributeSalary: %v", err)
	}

	// USD account should be net zero (salary in, exchange out)
	updatedUSD, _ := svc.accRepo.GetByID(context.Background(), usdAcc.ID)
	if updatedUSD.CurrentBalance != 0 {
		t.Errorf("USD balance = %f, want 0", updatedUSD.CurrentBalance)
	}

	// EGP account should have full salary: 1000 * 50 = 50000
	updatedEGP, _ := svc.accRepo.GetByID(context.Background(), egpAcc.ID)
	if updatedEGP.CurrentBalance != 50000 {
		t.Errorf("EGP balance = %f, want 50000", updatedEGP.CurrentBalance)
	}
}

func TestSalaryService_DistributeSalary_WithAllocations(t *testing.T) {
	svc, usdAcc, egpAcc := setupSalaryTest(t)

	// Create an additional EGP account for allocation
	db := testutil.NewTestDB(t)
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Bank2"})
	savingsAcc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "EGP Savings",
		Currency:       models.CurrencyEGP,
		InitialBalance: 0,
	})

	dist := SalaryDistribution{
		SalaryUSD:    1000,
		ExchangeRate: 50,
		USDAccountID: usdAcc.ID,
		EGPAccountID: egpAcc.ID,
		Allocations: []SalaryAllocation{
			{AccountID: savingsAcc.ID, Amount: 10000},
		},
		Date: time.Now(),
	}

	err := svc.DistributeSalary(context.Background(), dist)
	if err != nil {
		t.Fatalf("DistributeSalary: %v", err)
	}

	// EGP main should have 50000 - 10000 = 40000
	updatedEGP, _ := svc.accRepo.GetByID(context.Background(), egpAcc.ID)
	if updatedEGP.CurrentBalance != 40000 {
		t.Errorf("EGP main balance = %f, want 40000", updatedEGP.CurrentBalance)
	}

	// Savings should have 10000
	updatedSavings, _ := svc.accRepo.GetByID(context.Background(), savingsAcc.ID)
	if updatedSavings.CurrentBalance != 10000 {
		t.Errorf("savings balance = %f, want 10000", updatedSavings.CurrentBalance)
	}
}

func TestSalaryService_DistributeSalary_ValidationErrors(t *testing.T) {
	svc, usdAcc, egpAcc := setupSalaryTest(t)

	tests := []struct {
		name string
		dist SalaryDistribution
	}{
		{
			name: "zero salary",
			dist: SalaryDistribution{SalaryUSD: 0, ExchangeRate: 50, USDAccountID: usdAcc.ID, EGPAccountID: egpAcc.ID},
		},
		{
			name: "negative rate",
			dist: SalaryDistribution{SalaryUSD: 1000, ExchangeRate: -1, USDAccountID: usdAcc.ID, EGPAccountID: egpAcc.ID},
		},
		{
			name: "missing USD account",
			dist: SalaryDistribution{SalaryUSD: 1000, ExchangeRate: 50, USDAccountID: "", EGPAccountID: egpAcc.ID},
		},
		{
			name: "allocations exceed salary",
			dist: SalaryDistribution{
				SalaryUSD:    1000,
				ExchangeRate: 50,
				USDAccountID: usdAcc.ID,
				EGPAccountID: egpAcc.ID,
				Allocations:  []SalaryAllocation{{AccountID: "x", Amount: 60000}},
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := svc.DistributeSalary(context.Background(), tt.dist)
			if err == nil {
				t.Errorf("expected error for %s, got nil", tt.name)
			}
		})
	}
}
