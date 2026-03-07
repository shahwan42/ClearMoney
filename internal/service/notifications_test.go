package service

import (
	"context"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func TestNotificationService_GetPendingNotifications_Empty(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "recurring_rules")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	institutionRepo := repository.NewInstitutionRepo(db)
	accountRepo := repository.NewAccountRepo(db)
	txRepo := repository.NewTransactionRepo(db)
	dashSvc := NewDashboardService(institutionRepo, accountRepo, txRepo)

	recurringRepo := repository.NewRecurringRepo(db)
	recurringSvc := NewRecurringService(recurringRepo, NewTransactionService(txRepo, accountRepo))

	notifSvc := NewNotificationService(dashSvc, recurringSvc)
	ctx := context.Background()

	notifications, err := notifSvc.GetPendingNotifications(ctx)
	if err != nil {
		t.Fatalf("GetPendingNotifications: %v", err)
	}
	// With no credit cards due and no recurring rules, should be empty
	if len(notifications) != 0 {
		t.Errorf("expected 0 notifications, got %d", len(notifications))
	}
}

func TestNotificationService_NilServices(t *testing.T) {
	// Should work gracefully with nil services
	notifSvc := NewNotificationService(nil, nil)
	ctx := context.Background()

	notifications, err := notifSvc.GetPendingNotifications(ctx)
	if err != nil {
		t.Fatalf("GetPendingNotifications: %v", err)
	}
	if len(notifications) != 0 {
		t.Errorf("expected 0 notifications, got %d", len(notifications))
	}
}
