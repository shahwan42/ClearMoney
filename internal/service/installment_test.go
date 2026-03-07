package service

import (
	"context"
	"testing"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func setupInstallmentTest(t *testing.T) (*InstallmentService, models.Account) {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "installment_plans")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	installRepo := repository.NewInstallmentRepo(db)
	txSvc := NewTransactionService(txRepo, accRepo)
	svc := NewInstallmentService(installRepo, txSvc)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "TRU"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "TRU Credit",
		Type:           models.AccountTypeCreditCard,
		Currency:       models.CurrencyEGP,
		CreditLimit:    func() *float64 { v := 50000.0; return &v }(),
	})

	return svc, acc
}

func TestInstallmentService_Create(t *testing.T) {
	svc, acc := setupInstallmentTest(t)
	ctx := context.Background()

	plan, err := svc.Create(ctx, models.InstallmentPlan{
		AccountID:       acc.ID,
		Description:     "iPhone 16 Pro",
		TotalAmount:     60000,
		NumInstallments: 12,
		StartDate:       time.Now(),
	})

	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if plan.ID == "" {
		t.Fatal("expected plan ID")
	}
	if plan.MonthlyAmount != 5000 {
		t.Errorf("monthly_amount = %f, want 5000", plan.MonthlyAmount)
	}
	if plan.RemainingInstallments != 12 {
		t.Errorf("remaining = %d, want 12", plan.RemainingInstallments)
	}
}

func TestInstallmentService_Create_ValidationErrors(t *testing.T) {
	svc, acc := setupInstallmentTest(t)
	ctx := context.Background()

	tests := []struct {
		name string
		plan models.InstallmentPlan
	}{
		{"empty description", models.InstallmentPlan{AccountID: acc.ID, TotalAmount: 1000, NumInstallments: 3}},
		{"zero amount", models.InstallmentPlan{AccountID: acc.ID, Description: "X", NumInstallments: 3}},
		{"zero installments", models.InstallmentPlan{AccountID: acc.ID, Description: "X", TotalAmount: 1000}},
		{"no account", models.InstallmentPlan{Description: "X", TotalAmount: 1000, NumInstallments: 3}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := svc.Create(ctx, tt.plan)
			if err == nil {
				t.Error("expected error")
			}
		})
	}
}

func TestInstallmentService_RecordPayment(t *testing.T) {
	svc, acc := setupInstallmentTest(t)
	ctx := context.Background()

	plan, _ := svc.Create(ctx, models.InstallmentPlan{
		AccountID:       acc.ID,
		Description:     "Laptop",
		TotalAmount:     30000,
		NumInstallments: 3,
		StartDate:       time.Now(),
	})

	err := svc.RecordPayment(ctx, plan.ID)
	if err != nil {
		t.Fatalf("RecordPayment: %v", err)
	}

	// Verify remaining decreased
	plans, _ := svc.GetAll(ctx)
	if len(plans) != 1 {
		t.Fatalf("expected 1 plan, got %d", len(plans))
	}
	if plans[0].RemainingInstallments != 2 {
		t.Errorf("remaining = %d, want 2", plans[0].RemainingInstallments)
	}
}

func TestInstallmentService_Delete(t *testing.T) {
	svc, acc := setupInstallmentTest(t)
	ctx := context.Background()

	plan, _ := svc.Create(ctx, models.InstallmentPlan{
		AccountID:       acc.ID,
		Description:     "Test",
		TotalAmount:     1000,
		NumInstallments: 2,
		StartDate:       time.Now(),
	})

	err := svc.Delete(ctx, plan.ID)
	if err != nil {
		t.Fatalf("Delete: %v", err)
	}

	plans, _ := svc.GetAll(ctx)
	if len(plans) != 0 {
		t.Errorf("expected 0 plans after delete, got %d", len(plans))
	}
}
