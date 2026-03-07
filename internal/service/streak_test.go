package service

import (
	"context"
	"testing"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func setupStreakTest(t *testing.T) *StreakService {
	t.Helper()
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	return NewStreakService(db)
}

// insertTxOnDate inserts a minimal transaction for a given date (needs an account).
func insertTxOnDate(t *testing.T, svc *StreakService, accountID string, date time.Time) {
	t.Helper()
	_, err := svc.db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, date)
		VALUES ('expense', 10, 'EGP', $1, $2)
	`, accountID, date)
	if err != nil {
		t.Fatalf("insert tx: %v", err)
	}
}

func TestStreakService_NoTransactions(t *testing.T) {
	svc := setupStreakTest(t)

	info, err := svc.GetStreak(context.Background())
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
	svc := setupStreakTest(t)

	// Create an account to reference
	inst := testutil.CreateInstitution(t, svc.db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank,
	})
	acc := testutil.CreateAccount(t, svc.db, models.Account{
		Name: "Cash", InstitutionID: inst.ID, Currency: models.CurrencyEGP, Type: models.AccountTypeChecking,
	})

	// Insert transactions for today, yesterday, and day before
	today := time.Now().Truncate(24 * time.Hour)
	insertTxOnDate(t, svc, acc.ID, today)
	insertTxOnDate(t, svc, acc.ID, today.AddDate(0, 0, -1))
	insertTxOnDate(t, svc, acc.ID, today.AddDate(0, 0, -2))

	info, err := svc.GetStreak(context.Background())
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.ConsecutiveDays != 3 {
		t.Errorf("expected 3 consecutive days, got %d", info.ConsecutiveDays)
	}
}

func TestStreakService_BrokenStreak(t *testing.T) {
	svc := setupStreakTest(t)

	inst := testutil.CreateInstitution(t, svc.db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank,
	})
	acc := testutil.CreateAccount(t, svc.db, models.Account{
		Name: "Cash", InstitutionID: inst.ID, Currency: models.CurrencyEGP, Type: models.AccountTypeChecking,
	})

	// Today and 2 days ago (gap yesterday)
	today := time.Now().Truncate(24 * time.Hour)
	insertTxOnDate(t, svc, acc.ID, today)
	insertTxOnDate(t, svc, acc.ID, today.AddDate(0, 0, -2))

	info, err := svc.GetStreak(context.Background())
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.ConsecutiveDays != 1 {
		t.Errorf("expected 1 day (broken streak), got %d", info.ConsecutiveDays)
	}
}

func TestStreakService_WeeklyCount(t *testing.T) {
	svc := setupStreakTest(t)

	inst := testutil.CreateInstitution(t, svc.db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank,
	})
	acc := testutil.CreateAccount(t, svc.db, models.Account{
		Name: "Cash", InstitutionID: inst.ID, Currency: models.CurrencyEGP, Type: models.AccountTypeChecking,
	})

	// Insert 5 transactions today — weekly count should be 5
	today := time.Now().Truncate(24 * time.Hour)
	for i := 0; i < 5; i++ {
		insertTxOnDate(t, svc, acc.ID, today)
	}

	info, err := svc.GetStreak(context.Background())
	if err != nil {
		t.Fatalf("get streak: %v", err)
	}
	if info.WeeklyCount != 5 {
		t.Errorf("expected weekly count 5, got %d", info.WeeklyCount)
	}
}
