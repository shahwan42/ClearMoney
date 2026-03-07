package jobs

import (
	"context"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func TestReconcileBalances_NoDiscrepancy(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank,
	})
	acc := testutil.CreateAccount(t, db, models.Account{
		Name: "Cash", InstitutionID: inst.ID,
		Currency: models.CurrencyEGP, Type: models.AccountTypeChecking,
		InitialBalance: 1000,
	})

	// Insert a transaction with correct balance_delta
	_, err := db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, date, balance_delta)
		VALUES ('expense', 100, 'EGP', $1, CURRENT_DATE, -100)
	`, acc.ID)
	if err != nil {
		t.Fatalf("insert tx: %v", err)
	}

	// Update cached balance to match: 1000 + (-100) = 900
	_, err = db.Exec(`UPDATE accounts SET current_balance = 900 WHERE id = $1`, acc.ID)
	if err != nil {
		t.Fatalf("update balance: %v", err)
	}

	discrepancies, err := ReconcileBalances(context.Background(), db, false)
	if err != nil {
		t.Fatalf("reconcile: %v", err)
	}
	if len(discrepancies) != 0 {
		t.Errorf("expected 0 discrepancies, got %d: %+v", len(discrepancies), discrepancies)
	}
}

func TestReconcileBalances_DetectsDiscrepancy(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank,
	})
	acc := testutil.CreateAccount(t, db, models.Account{
		Name: "Cash", InstitutionID: inst.ID,
		Currency: models.CurrencyEGP, Type: models.AccountTypeChecking,
		InitialBalance: 1000,
	})

	// Insert a transaction with balance_delta
	_, err := db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, date, balance_delta)
		VALUES ('expense', 200, 'EGP', $1, CURRENT_DATE, -200)
	`, acc.ID)
	if err != nil {
		t.Fatalf("insert tx: %v", err)
	}

	// Set cached balance to WRONG value (should be 800, set to 900)
	_, err = db.Exec(`UPDATE accounts SET current_balance = 900 WHERE id = $1`, acc.ID)
	if err != nil {
		t.Fatalf("update balance: %v", err)
	}

	discrepancies, err := ReconcileBalances(context.Background(), db, false)
	if err != nil {
		t.Fatalf("reconcile: %v", err)
	}
	if len(discrepancies) != 1 {
		t.Fatalf("expected 1 discrepancy, got %d", len(discrepancies))
	}
	d := discrepancies[0]
	if d.CachedBalance != 900 {
		t.Errorf("expected cached 900, got %.2f", d.CachedBalance)
	}
	if d.ExpectedBalance != 800 {
		t.Errorf("expected 800, got %.2f", d.ExpectedBalance)
	}
}

func TestReconcileBalances_AutoFix(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	inst := testutil.CreateInstitution(t, db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank,
	})
	acc := testutil.CreateAccount(t, db, models.Account{
		Name: "Cash", InstitutionID: inst.ID,
		Currency: models.CurrencyEGP, Type: models.AccountTypeChecking,
		InitialBalance: 500,
	})

	// Insert transaction
	_, err := db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, date, balance_delta)
		VALUES ('income', 300, 'EGP', $1, CURRENT_DATE, 300)
	`, acc.ID)
	if err != nil {
		t.Fatalf("insert tx: %v", err)
	}

	// Set wrong cached balance
	_, err = db.Exec(`UPDATE accounts SET current_balance = 0 WHERE id = $1`, acc.ID)
	if err != nil {
		t.Fatalf("update balance: %v", err)
	}

	// Run with autoFix = true
	discrepancies, err := ReconcileBalances(context.Background(), db, true)
	if err != nil {
		t.Fatalf("reconcile: %v", err)
	}
	if len(discrepancies) != 1 {
		t.Fatalf("expected 1 discrepancy, got %d", len(discrepancies))
	}

	// Verify balance was fixed
	var balance float64
	err = db.QueryRow(`SELECT current_balance FROM accounts WHERE id = $1`, acc.ID).Scan(&balance)
	if err != nil {
		t.Fatalf("query balance: %v", err)
	}
	if balance != 800 {
		t.Errorf("expected fixed balance 800, got %.2f", balance)
	}
}
