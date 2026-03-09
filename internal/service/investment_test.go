// Tests for InvestmentService — covers CRUD, valuation updates, and total computation.
//
// These tests follow the same integration test pattern: clean DB, create data, verify.
// The setupInvestmentTest helper is intentionally simple — just cleans the table and
// creates the service. No accounts or transactions needed since investments are standalone.
package service

import (
	"context"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

// setupInvestmentTest creates a clean InvestmentService for testing.
func setupInvestmentTest(t *testing.T) *InvestmentService {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "investments")
	repo := repository.NewInvestmentRepo(db)
	return NewInvestmentService(repo)
}

func TestInvestmentService_Create(t *testing.T) {
	svc := setupInvestmentTest(t)
	ctx := context.Background()

	inv, err := svc.Create(ctx, models.Investment{
		Platform:      "Thndr",
		FundName:      "AZG",
		Units:         100.5,
		LastUnitPrice: 15.25,
		Currency:      models.CurrencyEGP,
	})

	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if inv.ID == "" {
		t.Fatal("expected investment ID")
	}
	if inv.FundName != "AZG" {
		t.Errorf("fund_name = %s, want AZG", inv.FundName)
	}
}

func TestInvestmentService_Create_ValidationErrors(t *testing.T) {
	svc := setupInvestmentTest(t)
	ctx := context.Background()

	tests := []struct {
		name string
		inv  models.Investment
	}{
		{"empty fund name", models.Investment{Units: 10, LastUnitPrice: 5}},
		{"zero units", models.Investment{FundName: "X", Units: 0, LastUnitPrice: 5}},
		{"negative price", models.Investment{FundName: "X", Units: 10, LastUnitPrice: -1}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := svc.Create(ctx, tt.inv)
			if err == nil {
				t.Error("expected error")
			}
		})
	}
}

func TestInvestmentService_UpdateValuation(t *testing.T) {
	svc := setupInvestmentTest(t)
	ctx := context.Background()

	inv, _ := svc.Create(ctx, models.Investment{
		FundName:      "BCO",
		Units:         50,
		LastUnitPrice: 10,
	})

	err := svc.UpdateValuation(ctx, inv.ID, 12.50)
	if err != nil {
		t.Fatalf("UpdateValuation: %v", err)
	}

	// Verify total valuation changed (50 * 12.50 = 625)
	total, _ := svc.GetTotalValuation(ctx)
	if total != 625 {
		t.Errorf("total = %f, want 625", total)
	}
}

func TestInvestmentService_GetTotalValuation(t *testing.T) {
	svc := setupInvestmentTest(t)
	ctx := context.Background()

	svc.Create(ctx, models.Investment{FundName: "A", Units: 100, LastUnitPrice: 10})
	svc.Create(ctx, models.Investment{FundName: "B", Units: 50, LastUnitPrice: 20})

	total, err := svc.GetTotalValuation(ctx)
	if err != nil {
		t.Fatalf("GetTotalValuation: %v", err)
	}
	// 100*10 + 50*20 = 2000
	if total != 2000 {
		t.Errorf("total = %f, want 2000", total)
	}
}

func TestInvestmentService_Delete(t *testing.T) {
	svc := setupInvestmentTest(t)
	ctx := context.Background()

	inv, _ := svc.Create(ctx, models.Investment{FundName: "X", Units: 10, LastUnitPrice: 5})

	err := svc.Delete(ctx, inv.ID)
	if err != nil {
		t.Fatalf("Delete: %v", err)
	}

	all, _ := svc.GetAll(ctx)
	if len(all) != 0 {
		t.Errorf("expected 0 investments after delete, got %d", len(all))
	}
}
