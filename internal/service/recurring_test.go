package service

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

// setupRecurringTest creates a clean environment with recurring service, account, and category.
func setupRecurringTest(t *testing.T) (*RecurringService, *TransactionService, models.Account, string) {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "recurring_rules")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	txRepo := repository.NewTransactionRepo(db)
	accRepo := repository.NewAccountRepo(db)
	recurringRepo := repository.NewRecurringRepo(db)
	txSvc := NewTransactionService(txRepo, accRepo)
	recurringSvc := NewRecurringService(recurringRepo, txSvc)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Test Bank"})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
	})
	catID := testutil.GetFirstCategoryID(t, db, models.CategoryTypeExpense)

	return recurringSvc, txSvc, acc, catID
}

func makeTemplate(t *testing.T, acc models.Account, catID string, amount float64) json.RawMessage {
	t.Helper()
	note := "Monthly rent"
	tmpl := models.TransactionTemplate{
		Type:       models.TransactionTypeExpense,
		Amount:     amount,
		Currency:   acc.Currency,
		AccountID:  acc.ID,
		CategoryID: &catID,
		Note:       &note,
	}
	data, err := json.Marshal(tmpl)
	if err != nil {
		t.Fatalf("marshaling template: %v", err)
	}
	return data
}

func TestRecurringService_Create(t *testing.T) {
	svc, _, acc, catID := setupRecurringTest(t)
	ctx := context.Background()

	rule, err := svc.Create(ctx, models.RecurringRule{
		TemplateTransaction: makeTemplate(t, acc, catID, 5000),
		Frequency:           models.RecurringFrequencyMonthly,
		NextDueDate:         time.Date(2026, 4, 1, 0, 0, 0, 0, time.UTC),
		IsActive:            true,
	})

	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if rule.ID == "" {
		t.Fatal("expected rule ID")
	}
	if rule.Frequency != models.RecurringFrequencyMonthly {
		t.Errorf("frequency = %s, want monthly", rule.Frequency)
	}
}

func TestRecurringService_Create_ValidationErrors(t *testing.T) {
	svc, _, _, _ := setupRecurringTest(t)
	ctx := context.Background()

	tests := []struct {
		name string
		rule models.RecurringRule
	}{
		{"empty template", models.RecurringRule{
			Frequency:   models.RecurringFrequencyMonthly,
			NextDueDate: time.Now(),
		}},
		{"empty frequency", models.RecurringRule{
			TemplateTransaction: json.RawMessage(`{"type":"expense"}`),
			NextDueDate:         time.Now(),
		}},
		{"zero due date", models.RecurringRule{
			TemplateTransaction: json.RawMessage(`{"type":"expense"}`),
			Frequency:           models.RecurringFrequencyMonthly,
		}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := svc.Create(ctx, tt.rule)
			if err == nil {
				t.Error("expected error")
			}
		})
	}
}

func TestRecurringService_ProcessDueRules_AutoConfirm(t *testing.T) {
	svc, _, acc, catID := setupRecurringTest(t)
	ctx := context.Background()

	// Create an auto-confirm rule due today
	_, err := svc.Create(ctx, models.RecurringRule{
		TemplateTransaction: makeTemplate(t, acc, catID, 1000),
		Frequency:           models.RecurringFrequencyMonthly,
		NextDueDate:         time.Now().AddDate(0, 0, -1), // yesterday = due
		IsActive:            true,
		AutoConfirm:         true,
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	processed, err := svc.ProcessDueRules(ctx)
	if err != nil {
		t.Fatalf("ProcessDueRules: %v", err)
	}
	if processed != 1 {
		t.Errorf("processed = %d, want 1", processed)
	}

	// Verify the rule's next_due_date was advanced
	rules, _ := svc.GetAll(ctx)
	if len(rules) != 1 {
		t.Fatalf("expected 1 rule, got %d", len(rules))
	}
	if !rules[0].NextDueDate.After(time.Now().AddDate(0, 0, -1)) {
		t.Error("expected next_due_date to be advanced")
	}
}

func TestRecurringService_ProcessDueRules_SkipsManual(t *testing.T) {
	svc, _, acc, catID := setupRecurringTest(t)
	ctx := context.Background()

	// Create a manual rule (auto_confirm=false) due today
	_, err := svc.Create(ctx, models.RecurringRule{
		TemplateTransaction: makeTemplate(t, acc, catID, 2000),
		Frequency:           models.RecurringFrequencyWeekly,
		NextDueDate:         time.Now().AddDate(0, 0, -1),
		IsActive:            true,
		AutoConfirm:         false,
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	processed, err := svc.ProcessDueRules(ctx)
	if err != nil {
		t.Fatalf("ProcessDueRules: %v", err)
	}
	if processed != 0 {
		t.Errorf("processed = %d, want 0 (manual rules should be skipped)", processed)
	}
}

func TestRecurringService_ConfirmRule(t *testing.T) {
	svc, _, acc, catID := setupRecurringTest(t)
	ctx := context.Background()

	rule, err := svc.Create(ctx, models.RecurringRule{
		TemplateTransaction: makeTemplate(t, acc, catID, 3000),
		Frequency:           models.RecurringFrequencyMonthly,
		NextDueDate:         time.Date(2026, 3, 1, 0, 0, 0, 0, time.UTC),
		IsActive:            true,
		AutoConfirm:         false,
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	err = svc.ConfirmRule(ctx, rule.ID)
	if err != nil {
		t.Fatalf("ConfirmRule: %v", err)
	}

	// Verify next_due_date advanced by 1 month
	rules, _ := svc.GetAll(ctx)
	if len(rules) != 1 {
		t.Fatalf("expected 1 rule, got %d", len(rules))
	}
	expected := time.Date(2026, 4, 1, 0, 0, 0, 0, time.UTC)
	if !rules[0].NextDueDate.Equal(expected) {
		t.Errorf("next_due_date = %v, want %v", rules[0].NextDueDate, expected)
	}
}

func TestRecurringService_SkipRule(t *testing.T) {
	svc, _, acc, catID := setupRecurringTest(t)
	ctx := context.Background()

	rule, err := svc.Create(ctx, models.RecurringRule{
		TemplateTransaction: makeTemplate(t, acc, catID, 1500),
		Frequency:           models.RecurringFrequencyWeekly,
		NextDueDate:         time.Date(2026, 3, 7, 0, 0, 0, 0, time.UTC),
		IsActive:            true,
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	err = svc.SkipRule(ctx, rule.ID)
	if err != nil {
		t.Fatalf("SkipRule: %v", err)
	}

	// Verify next_due_date advanced by 7 days (weekly)
	rules, _ := svc.GetAll(ctx)
	expected := time.Date(2026, 3, 14, 0, 0, 0, 0, time.UTC)
	if !rules[0].NextDueDate.Equal(expected) {
		t.Errorf("next_due_date = %v, want %v", rules[0].NextDueDate, expected)
	}
}

func TestRecurringService_Delete(t *testing.T) {
	svc, _, acc, catID := setupRecurringTest(t)
	ctx := context.Background()

	rule, _ := svc.Create(ctx, models.RecurringRule{
		TemplateTransaction: makeTemplate(t, acc, catID, 500),
		Frequency:           models.RecurringFrequencyMonthly,
		NextDueDate:         time.Now().AddDate(0, 1, 0),
		IsActive:            true,
	})

	err := svc.Delete(ctx, rule.ID)
	if err != nil {
		t.Fatalf("Delete: %v", err)
	}

	rules, _ := svc.GetAll(ctx)
	if len(rules) != 0 {
		t.Errorf("expected 0 rules after delete, got %d", len(rules))
	}
}

func TestRecurringService_GetDuePending(t *testing.T) {
	svc, _, acc, catID := setupRecurringTest(t)
	ctx := context.Background()

	// Create one auto and one manual, both due
	svc.Create(ctx, models.RecurringRule{
		TemplateTransaction: makeTemplate(t, acc, catID, 1000),
		Frequency:           models.RecurringFrequencyMonthly,
		NextDueDate:         time.Now().AddDate(0, 0, -1),
		IsActive:            true,
		AutoConfirm:         true,
	})
	svc.Create(ctx, models.RecurringRule{
		TemplateTransaction: makeTemplate(t, acc, catID, 2000),
		Frequency:           models.RecurringFrequencyMonthly,
		NextDueDate:         time.Now().AddDate(0, 0, -1),
		IsActive:            true,
		AutoConfirm:         false,
	})

	pending, err := svc.GetDuePending(ctx)
	if err != nil {
		t.Fatalf("GetDuePending: %v", err)
	}
	if len(pending) != 1 {
		t.Errorf("expected 1 pending rule, got %d", len(pending))
	}
}
