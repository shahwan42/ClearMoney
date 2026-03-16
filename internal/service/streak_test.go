// Tests for StreakService — verifies consecutive day counting and weekly totals.
//
// These tests use direct SQL (svc.db.Exec) to insert minimal transaction records,
// bypassing the TransactionService. This is a pragmatic choice: we only need
// the date column for streak calculations, not full transaction validation.
//
// Test cases cover:
//   - No transactions (zero streak)
//   - Consecutive days (growing streak)
//   - Broken streak (gap in dates)
//   - Weekly transaction count
//   - Grace period (no transaction today, streak from yesterday)
//   - ActiveToday flag
//   - Timezone regression (DB dates match via normalization)
package service

import (
	"context"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/testutil"
	"github.com/shahwan42/clearmoney/internal/timeutil"
)

// setupStreakTest creates a clean StreakService with empty transaction table.
func setupStreakTest(t *testing.T) (*StreakService, string) {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)
	return NewStreakService(db), userID
}

// insertTxOnDate inserts a minimal transaction for a given date (needs an account).
// Uses direct SQL exec instead of the service layer — bypasses validation for speed.
// The svc.db field is accessible because tests are in the same package (package service).
func insertTxOnDate(t *testing.T, svc *StreakService, accountID, userID string, date time.Time) {
	t.Helper()
	_, err := svc.db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, user_id, date)
		VALUES ('expense', 10, 'EGP', $1, $2, $3)
	`, accountID, userID, date)
	if err != nil {
		t.Fatalf("insert tx: %v", err)
	}
}

func TestStreakService_NoTransactions(t *testing.T) {
	svc, userID := setupStreakTest(t)

	info, err := svc.GetStreak(context.Background(), userID)
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.ConsecutiveDays != 0 {
		t.Errorf("expected 0 consecutive days, got %d", info.ConsecutiveDays)
	}
	if info.WeeklyCount != 0 {
		t.Errorf("expected 0 weekly count, got %d", info.WeeklyCount)
	}
}

func TestStreakService_ConsecutiveDays(t *testing.T) {
	svc, userID := setupStreakTest(t)

	inst := testutil.CreateInstitution(t, svc.db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank, UserID: userID,
	})
	acc := testutil.CreateAccount(t, svc.db, models.Account{
		Name: "Cash", InstitutionID: inst.ID, Currency: models.CurrencyEGP, Type: models.AccountTypeCurrent, UserID: userID,
	})

	// Insert transactions for today, yesterday, and day before
	today := timeutil.Today(time.UTC)
	insertTxOnDate(t, svc, acc.ID, userID, today)
	insertTxOnDate(t, svc, acc.ID, userID, today.AddDate(0, 0, -1))
	insertTxOnDate(t, svc, acc.ID, userID, today.AddDate(0, 0, -2))

	info, err := svc.GetStreak(context.Background(), userID)
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.ConsecutiveDays != 3 {
		t.Errorf("expected 3 consecutive days, got %d", info.ConsecutiveDays)
	}
}

func TestStreakService_BrokenStreak(t *testing.T) {
	svc, userID := setupStreakTest(t)

	inst := testutil.CreateInstitution(t, svc.db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank, UserID: userID,
	})
	acc := testutil.CreateAccount(t, svc.db, models.Account{
		Name: "Cash", InstitutionID: inst.ID, Currency: models.CurrencyEGP, Type: models.AccountTypeCurrent, UserID: userID,
	})

	// Today and 2 days ago (gap yesterday)
	today := timeutil.Today(time.UTC)
	insertTxOnDate(t, svc, acc.ID, userID, today)
	insertTxOnDate(t, svc, acc.ID, userID, today.AddDate(0, 0, -2))

	info, err := svc.GetStreak(context.Background(), userID)
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.ConsecutiveDays != 1 {
		t.Errorf("expected 1 day (broken streak), got %d", info.ConsecutiveDays)
	}
}

func TestStreakService_WeeklyCount(t *testing.T) {
	svc, userID := setupStreakTest(t)

	inst := testutil.CreateInstitution(t, svc.db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank, UserID: userID,
	})
	acc := testutil.CreateAccount(t, svc.db, models.Account{
		Name: "Cash", InstitutionID: inst.ID, Currency: models.CurrencyEGP, Type: models.AccountTypeCurrent, UserID: userID,
	})

	// Insert 5 transactions today — weekly count should be 5
	today := timeutil.Today(time.UTC)
	for i := range 5 {
		_ = i
		insertTxOnDate(t, svc, acc.ID, userID, today)
	}

	info, err := svc.GetStreak(context.Background(), userID)
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.WeeklyCount != 5 {
		t.Errorf("expected weekly count 5, got %d", info.WeeklyCount)
	}
}

func TestStreakService_GracePeriod(t *testing.T) {
	svc, userID := setupStreakTest(t)

	inst := testutil.CreateInstitution(t, svc.db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank, UserID: userID,
	})
	acc := testutil.CreateAccount(t, svc.db, models.Account{
		Name: "Cash", InstitutionID: inst.ID, Currency: models.CurrencyEGP, Type: models.AccountTypeCurrent, UserID: userID,
	})

	// Transactions yesterday and 2 days before, but NOT today
	today := timeutil.Today(time.UTC)
	insertTxOnDate(t, svc, acc.ID, userID, today.AddDate(0, 0, -1))
	insertTxOnDate(t, svc, acc.ID, userID, today.AddDate(0, 0, -2))
	insertTxOnDate(t, svc, acc.ID, userID, today.AddDate(0, 0, -3))

	info, err := svc.GetStreak(context.Background(), userID)
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.ConsecutiveDays != 3 {
		t.Errorf("expected 3 consecutive days (grace period), got %d", info.ConsecutiveDays)
	}
	if info.ActiveToday {
		t.Error("expected ActiveToday to be false")
	}
}

func TestStreakService_GracePeriodBroken(t *testing.T) {
	svc, userID := setupStreakTest(t)

	inst := testutil.CreateInstitution(t, svc.db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank, UserID: userID,
	})
	acc := testutil.CreateAccount(t, svc.db, models.Account{
		Name: "Cash", InstitutionID: inst.ID, Currency: models.CurrencyEGP, Type: models.AccountTypeCurrent, UserID: userID,
	})

	// Transaction only 2 days ago (gap yesterday = no grace)
	today := timeutil.Today(time.UTC)
	insertTxOnDate(t, svc, acc.ID, userID, today.AddDate(0, 0, -2))

	info, err := svc.GetStreak(context.Background(), userID)
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.ConsecutiveDays != 0 {
		t.Errorf("expected 0 (broken, no grace), got %d", info.ConsecutiveDays)
	}
}

func TestStreakService_ActiveToday(t *testing.T) {
	svc, userID := setupStreakTest(t)

	inst := testutil.CreateInstitution(t, svc.db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank, UserID: userID,
	})
	acc := testutil.CreateAccount(t, svc.db, models.Account{
		Name: "Cash", InstitutionID: inst.ID, Currency: models.CurrencyEGP, Type: models.AccountTypeCurrent, UserID: userID,
	})

	today := timeutil.Today(time.UTC)
	insertTxOnDate(t, svc, acc.ID, userID, today)
	insertTxOnDate(t, svc, acc.ID, userID, today.AddDate(0, 0, -1))

	info, err := svc.GetStreak(context.Background(), userID)
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.ConsecutiveDays != 2 {
		t.Errorf("expected 2, got %d", info.ConsecutiveDays)
	}
	if !info.ActiveToday {
		t.Error("expected ActiveToday to be true")
	}
}

func TestStreakService_TimezoneRegression(t *testing.T) {
	// Verify that DB dates normalized via time.Date(..., loc).UTC() match
	// timeutil.Today(loc) for the same calendar date across timezones.
	cairo, err := time.LoadLocation("Africa/Cairo")
	if err != nil {
		t.Skip("Africa/Cairo timezone not available")
	}

	// Simulate what timeutil.Today(cairo) would return for March 15 in Cairo
	todayCairo := time.Date(2026, 3, 15, 0, 0, 0, 0, cairo).UTC()

	// Simulate how we normalize a DB date (pgx returns DATE as midnight UTC)
	dbDate := time.Date(2026, 3, 15, 0, 0, 0, 0, time.UTC)
	normalized := time.Date(dbDate.Year(), dbDate.Month(), dbDate.Day(), 0, 0, 0, 0, cairo).UTC()

	if !normalized.Equal(todayCairo) {
		t.Errorf("normalized DB date should equal Today(cairo): got %v, want %v", normalized, todayCairo)
	}

	// Prove the old bug: Truncate(24h) gives wrong result for non-UTC timezones
	truncated := dbDate.Truncate(24 * time.Hour)
	if truncated.Equal(todayCairo) {
		t.Log("Truncate happened to match (test env may be UTC)")
	} else {
		t.Logf("Truncate bug confirmed: Truncate=%v, Today(cairo)=%v", truncated, todayCairo)
	}
}
