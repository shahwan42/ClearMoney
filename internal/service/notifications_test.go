// Tests for NotificationService — verifies notification generation logic.
//
// Two key tests:
//   1. Empty state: no credit cards due, no recurring rules → zero notifications
//   2. Nil services: constructor accepts nil for both dependencies → no panics
//
// The nil-safety test (TestNotificationService_NilServices) is important because
// it verifies the service degrades gracefully when optional dependencies are missing.
// This pattern is used throughout ClearMoney's services.
package service

import (
	"context"
	"testing"

	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// TestNotificationService_GetPendingNotifications_Empty verifies that a clean database
// produces zero notifications (no due credit cards, no pending recurring rules).
func TestNotificationService_GetPendingNotifications_Empty(t *testing.T) {
	db := testutil.NewTestDB(t)
	userID := testutil.SetupTestUser(t, db)
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

	notifications, err := notifSvc.GetPendingNotifications(ctx, userID)
	if err != nil {
		t.Fatalf("GetPendingNotifications: %v", err)
	}
	// With no credit cards due and no recurring rules, should be empty
	if len(notifications) != 0 {
		t.Errorf("expected 0 notifications, got %d", len(notifications))
	}
}

// TestNotificationService_NilServices verifies nil-safety — the service handles
// nil dependencies without panicking. This is crucial because some features may
// be disabled (e.g., no database connection at startup).
func TestNotificationService_NilServices(t *testing.T) {
	// Passing nil for both services — must not panic
	notifSvc := NewNotificationService(nil, nil)
	ctx := context.Background()

	notifications, err := notifSvc.GetPendingNotifications(ctx, "nonexistent-user")
	if err != nil {
		t.Fatalf("GetPendingNotifications: %v", err)
	}
	if len(notifications) != 0 {
		t.Errorf("expected 0 notifications, got %d", len(notifications))
	}
}
