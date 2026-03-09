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

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

// TestReconcileBalances_NoDiscrepancy verifies that reconciliation passes
// when cached balance matches computed balance (the happy path).
//
// Test naming convention in Go: TestFunctionName_Scenario
// This is similar to PHPUnit's test_function_name_scenario or pytest's
// test_function_name_when_condition pattern.
func TestReconcileBalances_NoDiscrepancy(t *testing.T) {
	// ARRANGE: Set up test database and create test data.
	// NewTestDB connects to the test database and runs migrations.
	// If TEST_DATABASE_URL is not set, the test is skipped (not failed).
	db := testutil.NewTestDB(t)

	// Clean tables in dependency order (transactions depends on accounts,
	// accounts depends on institutions). CleanTable uses TRUNCATE CASCADE
	// so order doesn't strictly matter, but it documents the dependencies.
	testutil.CleanTable(t, db, "transactions")
	testutil.CleanTable(t, db, "accounts")
	testutil.CleanTable(t, db, "institutions")

	// Factory helpers create test data with sensible defaults.
	// Override only the fields you care about — similar to Laravel's
	// Institution::factory()->create(['name' => 'Test Bank']).
	inst := testutil.CreateInstitution(t, db, models.Institution{
		Name: "Test Bank", Type: models.InstitutionTypeBank,
	})
	acc := testutil.CreateAccount(t, db, models.Account{
		Name: "Cash", InstitutionID: inst.ID,
		Currency: models.CurrencyEGP, Type: models.AccountTypeChecking,
		InitialBalance: 1000,
	})

	// Insert a transaction with correct balance_delta using raw SQL.
	// In Go tests, it's common to use raw SQL for setup data that doesn't
	// need a factory — especially when testing the exact SQL logic.
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

	// ACT: Run reconciliation with autoFix=false (report only, don't fix).
	// context.Background() creates a non-cancellable context — fine for tests.
	discrepancies, err := ReconcileBalances(context.Background(), db, false)

	// ASSERT: Expect no errors and no discrepancies.
	if err != nil {
		t.Fatalf("reconcile: %v", err)
	}
	if len(discrepancies) != 0 {
		// %+v prints struct field names — useful for debugging test failures.
		// Output: [{AccountID:abc AccountName:Cash CachedBalance:900 ...}]
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

	// Set cached balance to WRONG value (should be 800, set to 900).
	// This simulates what happens if a bug causes the balance to drift.
	_, err = db.Exec(`UPDATE accounts SET current_balance = 900 WHERE id = $1`, acc.ID)
	if err != nil {
		t.Fatalf("update balance: %v", err)
	}

	// ACT
	discrepancies, err := ReconcileBalances(context.Background(), db, false)

	// ASSERT: Expect exactly 1 discrepancy with the correct values.
	if err != nil {
		t.Fatalf("reconcile: %v", err)
	}
	// t.Fatalf stops the test here if the precondition fails, preventing a
	// nil-pointer panic on discrepancies[0] below. This is a common Go pattern:
	// use Fatalf for preconditions, Errorf for the actual assertions.
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
//
// This test follows the "Arrange, Act, Assert, Verify Side Effect" pattern:
// after calling the function, we query the database to confirm the fix was applied.
// This is similar to Laravel's assertDatabaseHas() or Django's assertQuerysetEqual().
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

	// Insert transaction: income of 300, so expected balance = 500 + 300 = 800
	_, err := db.Exec(`
		INSERT INTO transactions (type, amount, currency, account_id, date, balance_delta)
		VALUES ('income', 300, 'EGP', $1, CURRENT_DATE, 300)
	`, acc.ID)
	if err != nil {
		t.Fatalf("insert tx: %v", err)
	}

	// Set wrong cached balance (0 instead of 800)
	_, err = db.Exec(`UPDATE accounts SET current_balance = 0 WHERE id = $1`, acc.ID)
	if err != nil {
		t.Fatalf("update balance: %v", err)
	}

	// ACT: Run with autoFix = true — this should UPDATE the database
	discrepancies, err := ReconcileBalances(context.Background(), db, true)
	if err != nil {
		t.Fatalf("reconcile: %v", err)
	}
	if len(discrepancies) != 1 {
		t.Fatalf("expected 1 discrepancy, got %d", len(discrepancies))
	}

	// VERIFY SIDE EFFECT: Query the database to confirm the balance was fixed.
	// db.QueryRow().Scan() is Go's way of fetching a single value from the DB.
	// This is like Laravel's DB::table('accounts')->value('current_balance')
	// or Django's Account.objects.values_list('current_balance', flat=True).first()
	var balance float64
	err = db.QueryRow(`SELECT current_balance FROM accounts WHERE id = $1`, acc.ID).Scan(&balance)
	if err != nil {
		t.Fatalf("query balance: %v", err)
	}
	if balance != 800 {
		t.Errorf("expected fixed balance 800, got %.2f", balance)
	}
}
