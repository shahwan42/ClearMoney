// Integration tests for VirtualAccountRepo.
//
// Tests the exclude_from_net_worth feature: GetTotalExcludedBalance and
// GetExcludedBalanceByAccountID return correct sums of excluded VA balances.
package repository

import (
	"context"
	"testing"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

func setupVirtualAccountTest(t *testing.T) (*VirtualAccountRepo, string, models.Institution, models.Account) {
	t.Helper()
	db := testutil.NewTestDB(t)
	userID := testutil.SetupTestUser(t, db)
	testutil.CleanTable(t, db, "virtual_account_allocations")
	testutil.CleanTable(t, db, "virtual_accounts")
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Test Bank", UserID: userID})
	acc := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Savings",
		Type:           models.AccountTypeSavings,
		Currency:       models.CurrencyEGP,
		InitialBalance: 100000,
		UserID:         userID,
	})
	return NewVirtualAccountRepo(db), userID, inst, acc
}

// TestVirtualAccountRepo_GetTotalExcludedBalance verifies that only excluded,
// non-archived VAs are summed.
func TestVirtualAccountRepo_GetTotalExcludedBalance(t *testing.T) {
	repo, userID, _, acc := setupVirtualAccountTest(t)
	db := testutil.NewTestDB(t)
	ctx := context.Background()

	// Create excluded VA with 30000 balance (using testutil to set current_balance directly)
	testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name: "Building Fund", Color: "#ff0000", CurrentBalance: 30000,
		AccountID: &acc.ID, ExcludeFromNetWorth: true, UserID: userID,
	})
	// Create normal VA (not excluded)
	testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name: "Emergency", Color: "#00ff00", CurrentBalance: 20000,
		AccountID: &acc.ID, ExcludeFromNetWorth: false, UserID: userID,
	})
	// Create archived excluded VA (should not be counted)
	testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name: "Old Fund", Color: "#0000ff", CurrentBalance: 10000,
		AccountID: &acc.ID, ExcludeFromNetWorth: true, IsArchived: true, UserID: userID,
	})

	total, err := repo.GetTotalExcludedBalance(ctx, userID)
	if err != nil {
		t.Fatalf("GetTotalExcludedBalance: %v", err)
	}
	if total != 30000 {
		t.Errorf("expected total excluded 30000, got %f", total)
	}
}

// TestVirtualAccountRepo_GetExcludedBalanceByAccountID verifies per-account
// excluded balance computation.
func TestVirtualAccountRepo_GetExcludedBalanceByAccountID(t *testing.T) {
	repo, userID, inst, acc := setupVirtualAccountTest(t)
	db := testutil.NewTestDB(t)
	ctx := context.Background()

	// Create another account
	acc2 := testutil.CreateAccount(t, db, models.Account{
		InstitutionID:  inst.ID,
		Name:           "Checking",
		Type:           models.AccountTypeCurrent,
		Currency:       models.CurrencyEGP,
		InitialBalance: 50000,
		UserID:         userID,
	})

	// Excluded VA linked to first account
	testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name: "Building Fund", Color: "#ff0000", CurrentBalance: 30000,
		AccountID: &acc.ID, ExcludeFromNetWorth: true, UserID: userID,
	})
	// Excluded VA linked to second account
	testutil.CreateVirtualAccount(t, db, models.VirtualAccount{
		Name: "Other Fund", Color: "#00ff00", CurrentBalance: 15000,
		AccountID: &acc2.ID, ExcludeFromNetWorth: true, UserID: userID,
	})

	// First account should show 30000
	bal1, err := repo.GetExcludedBalanceByAccountID(ctx, userID, acc.ID)
	if err != nil {
		t.Fatalf("GetExcludedBalanceByAccountID: %v", err)
	}
	if bal1 != 30000 {
		t.Errorf("expected 30000 for first account, got %f", bal1)
	}

	// Second account should show 15000
	bal2, err := repo.GetExcludedBalanceByAccountID(ctx, userID, acc2.ID)
	if err != nil {
		t.Fatalf("GetExcludedBalanceByAccountID: %v", err)
	}
	if bal2 != 15000 {
		t.Errorf("expected 15000 for second account, got %f", bal2)
	}
}

// TestVirtualAccountRepo_GetTotalExcludedBalance_Empty verifies zero returned
// when no excluded VAs exist.
func TestVirtualAccountRepo_GetTotalExcludedBalance_Empty(t *testing.T) {
	repo, userID, _, _ := setupVirtualAccountTest(t)
	ctx := context.Background()

	total, err := repo.GetTotalExcludedBalance(ctx, userID)
	if err != nil {
		t.Fatalf("GetTotalExcludedBalance: %v", err)
	}
	if total != 0 {
		t.Errorf("expected 0, got %f", total)
	}
}

// TestVirtualAccountRepo_CreateWithExclude verifies exclude_from_net_worth is
// persisted and returned correctly.
func TestVirtualAccountRepo_CreateWithExclude(t *testing.T) {
	repo, userID, _, acc := setupVirtualAccountTest(t)
	ctx := context.Background()

	created, err := repo.Create(ctx, userID, models.VirtualAccount{
		Name: "Building Fund", Color: "#ff0000",
		AccountID: &acc.ID, ExcludeFromNetWorth: true,
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if !created.ExcludeFromNetWorth {
		t.Error("expected ExcludeFromNetWorth to be true")
	}

	// Verify GetByID also returns it
	fetched, err := repo.GetByID(ctx, userID, created.ID)
	if err != nil {
		t.Fatalf("GetByID: %v", err)
	}
	if !fetched.ExcludeFromNetWorth {
		t.Error("expected ExcludeFromNetWorth to be true after GetByID")
	}
}

// TestVirtualAccountRepo_UpdateExclude verifies toggling the exclude flag.
func TestVirtualAccountRepo_UpdateExclude(t *testing.T) {
	repo, userID, _, acc := setupVirtualAccountTest(t)
	ctx := context.Background()

	created, _ := repo.Create(ctx, userID, models.VirtualAccount{
		Name: "Building Fund", Color: "#ff0000",
		AccountID: &acc.ID, ExcludeFromNetWorth: false,
	})

	// Toggle on
	created.ExcludeFromNetWorth = true
	if err := repo.Update(ctx, userID, created); err != nil {
		t.Fatalf("Update: %v", err)
	}

	fetched, _ := repo.GetByID(ctx, userID, created.ID)
	if !fetched.ExcludeFromNetWorth {
		t.Error("expected ExcludeFromNetWorth true after update")
	}

	// Toggle off
	fetched.ExcludeFromNetWorth = false
	if err := repo.Update(ctx, userID, fetched); err != nil {
		t.Fatalf("Update: %v", err)
	}

	fetched2, _ := repo.GetByID(ctx, userID, created.ID)
	if fetched2.ExcludeFromNetWorth {
		t.Error("expected ExcludeFromNetWorth false after second update")
	}
}
