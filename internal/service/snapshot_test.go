// Tests for SnapshotService — verifies daily snapshot creation, idempotency, and backfill.
package service

import (
	"context"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

func TestSnapshotService_TakeSnapshot(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "account_snapshots")
	testutil.CleanTable(t, db, "daily_snapshots")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC", UserID: userID})
	acc1 := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeCurrent,
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
		UserID:         userID,
	})
	acc2 := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Type:           models.AccountTypeSavings,
		Currency:       models.CurrencyEGP,
		InitialBalance: 100000,
		UserID:         userID,
	})

	snapshotRepo := repository.NewSnapshotRepo(db)
	accountRepo := repository.NewAccountRepo(db)
	institutionRepo := repository.NewInstitutionRepo(db)
	exchangeRateRepo := repository.NewExchangeRateRepo(db)
	svc := NewSnapshotService(snapshotRepo, accountRepo, institutionRepo, exchangeRateRepo)

	err := svc.TakeSnapshot(context.Background(), userID)
	if err != nil {
		t.Fatalf("TakeSnapshot: %v", err)
	}

	today := time.Now().Truncate(24 * time.Hour)
	exists, err := snapshotRepo.Exists(context.Background(), userID, today)
	if err != nil {
		t.Fatalf("Exists: %v", err)
	}
	if !exists {
		t.Error("expected today's snapshot to exist")
	}

	snapshots, err := snapshotRepo.GetDailyRange(context.Background(), userID, today, today)
	if err != nil {
		t.Fatalf("GetDailyRange: %v", err)
	}
	if len(snapshots) != 1 {
		t.Fatalf("expected 1 snapshot, got %d", len(snapshots))
	}
	snap := snapshots[0]
	expectedNetWorth := 150000.0
	if snap.NetWorthEGP != expectedNetWorth {
		t.Errorf("expected net worth EGP %f, got %f", expectedNetWorth, snap.NetWorthEGP)
	}
	if snap.NetWorthRaw != expectedNetWorth {
		t.Errorf("expected net worth raw %f, got %f", expectedNetWorth, snap.NetWorthRaw)
	}

	acc1Snaps, err := snapshotRepo.GetAccountRange(context.Background(), userID, acc1.ID, today, today)
	if err != nil {
		t.Fatalf("GetAccountRange acc1: %v", err)
	}
	if len(acc1Snaps) != 1 || acc1Snaps[0].Balance != 50000 {
		t.Errorf("expected acc1 balance 50000, got %v", acc1Snaps)
	}

	acc2Snaps, err := snapshotRepo.GetAccountRange(context.Background(), userID, acc2.ID, today, today)
	if err != nil {
		t.Fatalf("GetAccountRange acc2: %v", err)
	}
	if len(acc2Snaps) != 1 || acc2Snaps[0].Balance != 100000 {
		t.Errorf("expected acc2 balance 100000, got %v", acc2Snaps)
	}
}

func TestSnapshotService_Idempotent(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "account_snapshots")
	testutil.CleanTable(t, db, "daily_snapshots")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB", UserID: userID})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 10000,
		UserID:         userID,
	})

	snapshotRepo := repository.NewSnapshotRepo(db)
	svc := NewSnapshotService(snapshotRepo,
		repository.NewAccountRepo(db),
		repository.NewInstitutionRepo(db),
		repository.NewExchangeRateRepo(db),
	)

	if err := svc.TakeSnapshot(context.Background(), userID); err != nil {
		t.Fatalf("first TakeSnapshot: %v", err)
	}
	if err := svc.TakeSnapshot(context.Background(), userID); err != nil {
		t.Fatalf("second TakeSnapshot: %v", err)
	}

	today := time.Now().Truncate(24 * time.Hour)
	snaps, err := snapshotRepo.GetDailyRange(context.Background(), userID, today, today)
	if err != nil {
		t.Fatalf("GetDailyRange: %v", err)
	}
	if len(snaps) != 1 {
		t.Errorf("expected 1 snapshot (idempotent), got %d", len(snaps))
	}
}

func TestSnapshotService_BackfillSnapshots(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "account_snapshots")
	testutil.CleanTable(t, db, "daily_snapshots")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "HSBC", UserID: userID})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 20000,
		UserID:         userID,
	})

	svc := NewSnapshotService(
		repository.NewSnapshotRepo(db),
		repository.NewAccountRepo(db),
		repository.NewInstitutionRepo(db),
		repository.NewExchangeRateRepo(db),
	)

	count, err := svc.BackfillSnapshots(context.Background(), userID, 7)
	if err != nil {
		t.Fatalf("BackfillSnapshots: %v", err)
	}
	if count != 8 {
		t.Errorf("expected 8 backfilled days, got %d", count)
	}

	count2, err := svc.BackfillSnapshots(context.Background(), userID, 7)
	if err != nil {
		t.Fatalf("second BackfillSnapshots: %v", err)
	}
	if count2 != 0 {
		t.Errorf("expected 0 backfilled on second run, got %d", count2)
	}
}

func TestSnapshotService_GetNetWorthHistory(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "account_snapshots")
	testutil.CleanTable(t, db, "daily_snapshots")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB", UserID: userID})
	testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Currency:       models.CurrencyEGP,
		InitialBalance: 30000,
		UserID:         userID,
	})

	snapshotRepo := repository.NewSnapshotRepo(db)
	svc := NewSnapshotService(snapshotRepo,
		repository.NewAccountRepo(db),
		repository.NewInstitutionRepo(db),
		repository.NewExchangeRateRepo(db),
	)

	svc.BackfillSnapshots(context.Background(), userID, 5)

	values, err := svc.GetNetWorthHistory(context.Background(), userID, 5)
	if err != nil {
		t.Fatalf("GetNetWorthHistory: %v", err)
	}
	if len(values) == 0 {
		t.Error("expected non-empty net worth history")
	}
	for i, v := range values {
		if v != 30000 {
			t.Errorf("day %d: expected 30000, got %f", i, v)
		}
	}
}

func TestSnapshotService_GetAccountHistory(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "account_snapshots")
	testutil.CleanTable(t, db, "daily_snapshots")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB", UserID: userID})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Currency:       models.CurrencyEGP,
		InitialBalance: 75000,
		UserID:         userID,
	})

	svc := NewSnapshotService(
		repository.NewSnapshotRepo(db),
		repository.NewAccountRepo(db),
		repository.NewInstitutionRepo(db),
		repository.NewExchangeRateRepo(db),
	)

	svc.BackfillSnapshots(context.Background(), userID, 3)

	values, err := svc.GetAccountHistory(context.Background(), userID, acc.ID, 3)
	if err != nil {
		t.Fatalf("GetAccountHistory: %v", err)
	}
	if len(values) == 0 {
		t.Error("expected non-empty account history")
	}
	for i, v := range values {
		if v != 75000 {
			t.Errorf("day %d: expected 75000, got %f", i, v)
		}
	}
}
