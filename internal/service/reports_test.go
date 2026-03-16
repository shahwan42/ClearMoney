// Tests for ReportsService — validates monthly spending reports and income/expense summaries.
//
// These tests demonstrate a common integration test pattern: use one service (TransactionService)
// to create test data, then use another service (ReportsService) to verify the aggregated output.
// This is like seeding data with a factory and then testing a reporting endpoint.
package service

import (
	"context"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// TestReportsService_GetMonthlyReport creates expenses and income in the current month,
// then verifies the report correctly sums spending and computes income/expense/net.
func TestReportsService_GetMonthlyReport(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	userID := testutil.SetupTestUser(t, db)

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	txSvc := NewTransactionService(txRepo, accRepo)
	reportsSvc := NewReportsService(db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB", UserID: userID})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID: inst.ID, Name: "Main", Currency: models.CurrencyEGP, InitialBalance: 100000, UserID: userID,
	})
	catID := testutil.GetFirstCategoryID(t, db, models.CategoryTypeExpense)

	ctx := context.Background()
	now := time.Now()

	// Create expenses in current month
	txSvc.Create(ctx, userID, models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 5000,
		Currency: models.CurrencyEGP, AccountID: acc.ID, CategoryID: &catID,
		Date: now,
	})
	txSvc.Create(ctx, userID, models.Transaction{
		Type: models.TransactionTypeExpense, Amount: 3000,
		Currency: models.CurrencyEGP, AccountID: acc.ID, CategoryID: &catID,
		Date: now,
	})

	// Create income in current month
	txSvc.Create(ctx, userID, models.Transaction{
		Type: models.TransactionTypeIncome, Amount: 20000,
		Currency: models.CurrencyEGP, AccountID: acc.ID,
		Date: now,
	})

	report, err := reportsSvc.GetMonthlyReport(ctx, userID, now.Year(), now.Month(), ReportFilter{})
	if err != nil {
		t.Fatalf("GetMonthlyReport: %v", err)
	}

	// Total spending: 5000 + 3000 = 8000
	if report.TotalSpending != 8000 {
		t.Errorf("TotalSpending = %f, want 8000", report.TotalSpending)
	}

	// Should have spending categories
	if len(report.SpendingByCategory) == 0 {
		t.Error("expected spending categories")
	}

	// Current month: income=20000, expenses=8000
	if report.CurrentMonth.Income != 20000 {
		t.Errorf("Income = %f, want 20000", report.CurrentMonth.Income)
	}
	if report.CurrentMonth.Expenses != 8000 {
		t.Errorf("Expenses = %f, want 8000", report.CurrentMonth.Expenses)
	}
	if report.CurrentMonth.Net != 12000 {
		t.Errorf("Net = %f, want 12000", report.CurrentMonth.Net)
	}
}

// TestReportsService_GetMonthlyReport_EmptyMonth verifies the report handles months with
// no transactions — all totals should be zero, no categories returned.
func TestReportsService_GetMonthlyReport_EmptyMonth(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")

	userID := testutil.SetupTestUser(t, db)

	reportsSvc := NewReportsService(db)

	report, err := reportsSvc.GetMonthlyReport(context.Background(), userID, 2025, 1, ReportFilter{})
	if err != nil {
		t.Fatalf("GetMonthlyReport: %v", err)
	}

	if report.TotalSpending != 0 {
		t.Errorf("expected 0 spending, got %f", report.TotalSpending)
	}
	if len(report.SpendingByCategory) != 0 {
		t.Errorf("expected 0 categories, got %d", len(report.SpendingByCategory))
	}
}
