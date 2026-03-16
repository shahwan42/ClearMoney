// reconcile_test.go — Integration tests for the balance reconciliation job.
//
// # Go Testing Patterns (for Laravel/Django developers)
//
// Go's testing approach is fundamentally different from PHPUnit or pytest:
//
//   - No test classes:  Tests are plain functions named Test<Name>(t *testing.T).
//                       This is unlike PHPUnit's class-based tests or pytest's
//                       class-based test organization.
//
//   - No assertions lib: Go's stdlib has t.Error/t.Fatal instead of assertEquals.
//                        t.Error marks failure but continues; t.Fatal stops the test.
//                        This is like PHPUnit's $this->assertEquals() vs $this->fail().
//
//   - No setUp/tearDown: Go uses t.Cleanup() for teardown and helper functions for
//                        setup. This is more explicit than PHPUnit's setUp() or
//                        pytest's fixtures.
//
//   - Same package:     Tests in the same package can access unexported (private)
//                       functions. This file is in package `jobs`, so it can test
//                       internal details of reconcile.go directly.
//
//   - t.Fatalf vs t.Errorf:
//       - t.Fatalf: stops the test immediately (like PHPUnit's fail() or pytest.fail())
//       - t.Errorf: records the failure but continues (like soft assertions)
//       Use t.Fatalf for setup failures and preconditions; use t.Errorf for assertions
//       where you want to see all failures at once.
//
// # Integration Test Pattern
//
// These tests use a real PostgreSQL database (not mocks). This is similar to
// Laravel's RefreshDatabase trait or Django's TransactionTestCase. The pattern is:
//
//   1. testutil.NewTestDB(t)     — connects to test DB, runs migrations (setUp)
//   2. testutil.CleanTable(...)  — empties tables for a clean slate (truncate)
//   3. testutil.CreateX(...)     — inserts test data via factory helpers (arrange)
//   4. Call the function          — run the code under test (act)
//   5. Assert with t.Errorf       — check results (assert)
//
// Run with: TEST_DATABASE_URL=... go test -p 1 ./internal/jobs/
// The -p 1 flag runs test packages sequentially (they share a database).
//
// See: https://pkg.go.dev/testing
// See: https://go.dev/doc/tutorial/add-a-test
package jobs

import (
	"context"
	"testing"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// TestReconcileBalances_NoDiscrepancy verifies that reconciliation passes
// when cached balance matches computed balance (the happy path).
//
// Test naming convention in Go: TestFunctionName_Scenario
// This is similar to PHPUnit's test_function_name_scenario or pytest's
// test_function_name_when_condition pattern.
func TestReconcileBalances_NoDiscrepancy(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank, UserID: userID,
	})
	acc := testutil.CreateAccount(t, db, models.Account{
		Name: "Cash", InstitutionID: inst.ID,
		Currency: models.CurrencyEGP, Type: models.AccountTypeCurrent,
		InitialBalance: 1000, UserID: userID,
	})

	_, err := db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, user_id, date, balance_delta)
		VALUES ('expense', 100, 'EGP', $1, $2, CURRENT_DATE, -100)
	`, acc.ID, userID)
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

// TestReconcileBalances_DetectsDiscrepancy verifies that reconciliation catches
// a balance mismatch when the cached balance is wrong.
func TestReconcileBalances_DetectsDiscrepancy(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank, UserID: userID,
	})
	acc := testutil.CreateAccount(t, db, models.Account{
		Name: "Cash", InstitutionID: inst.ID,
		Currency: models.CurrencyEGP, Type: models.AccountTypeCurrent,
		InitialBalance: 1000, UserID: userID,
	})

	_, err := db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, user_id, date, balance_delta)
		VALUES ('expense', 200, 'EGP', $1, $2, CURRENT_DATE, -200)
	`, acc.ID, userID)
	if err != nil {
		t.Fatalf("insert tx: %v", err)
	}

	// Set cached balance to WRONG value (should be 800, set to 900).
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

// TestReconcileBalances_AutoFix verifies that autoFix=true actually updates
// the database to correct the cached balance.
func TestReconcileBalances_AutoFix(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")
	userID := testutil.SetupTestUser(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank, UserID: userID,
	})
	acc := testutil.CreateAccount(t, db, models.Account{
		Name: "Cash", InstitutionID: inst.ID,
		Currency: models.CurrencyEGP, Type: models.AccountTypeCurrent,
		InitialBalance: 500, UserID: userID,
	})

	// Insert transaction: income of 300, so expected balance = 500 + 300 = 800
	_, err := db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, user_id, date, balance_delta)
		VALUES ('income', 300, 'EGP', $1, $2, CURRENT_DATE, 300)
	`, acc.ID, userID)
	if err != nil {
		t.Fatalf("insert tx: %v", err)
	}

	// Set wrong cached balance (0 instead of 800)
	_, err = db.Exec(`UPDATE accounts SET current_balance = 0 WHERE id = $1`, acc.ID)
	if err != nil {
		t.Fatalf("update balance: %v", err)
	}

	discrepancies, err := ReconcileBalances(context.Background(), db, true)
	if err != nil {
		t.Fatalf("reconcile: %v", err)
	}
	if len(discrepancies) != 1 {
		t.Fatalf("expected 1 discrepancy, got %d", len(discrepancies))
	}

	// Verify the balance was fixed
	var balance float64
	err = db.QueryRow(`SELECT current_balance FROM accounts WHERE id = $1`, acc.ID).Scan(&balance)
	if err != nil {
		t.Fatalf("query balance: %v", err)
	}
	if balance != 800 {
		t.Errorf("expected fixed balance 800, got %.2f", balance)
	}
}
