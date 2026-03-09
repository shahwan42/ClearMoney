// Test file for the database connection package.
//
// Go testing primer for Laravel/Django developers:
//
// - Test files MUST end in _test.go (Go compiler enforces this).
// - Test functions MUST start with "Test" and take *testing.T as the only param.
// - Run tests with: go test ./internal/database/ -v
// - No PHPUnit or pytest needed — testing is built into the Go toolchain.
//
// Go concept — testing.T:
//   The *testing.T parameter is your test context (like $this in PHPUnit or self in pytest).
//   Key methods:
//     t.Fatal/t.Fatalf  — fail and STOP the test immediately (like $this->fail() in PHPUnit)
//     t.Error/t.Errorf  — fail but CONTINUE running (lets you see all failures at once)
//     t.Skip             — skip the test (like @skip in PHPUnit or @pytest.mark.skip)
//     t.Helper()         — marks a function as a test helper (cleans up stack traces)
//
// These tests are INTEGRATION tests — they need a real PostgreSQL database.
// They're skipped automatically if TEST_DATABASE_URL is not set, so `go test`
// works even without a database running (unit tests still pass).
//
// See: https://pkg.go.dev/testing — the standard library testing package
// See: https://go.dev/doc/tutorial/add-a-test — official testing tutorial
package database

import (
	"context"
	"os"
	"testing"
	"time"
)

// getTestDatabaseURL is a test helper that reads the DB URL from the environment.
//
// Go concept — t.Helper():
//   Marks this function as a test helper. When a test fails inside a helper,
//   Go reports the line number in the CALLING test function (not this helper),
//   making error messages much more useful. Always call t.Helper() in shared
//   test utility functions.
//
// Go concept — t.Skip():
//   Skips the test with a message (test passes but is marked as "skipped").
//   We use this to gracefully skip integration tests when no DB is available.
//   Laravel equivalent: $this->markTestSkipped() in PHPUnit.
//   Django equivalent:  @skipUnless(condition) decorator.
//
// This function is shared across test files in the same package (database).
// In Go, all _test.go files in a package can see each other's unexported
// (lowercase) functions — no need to import them.
func getTestDatabaseURL(t *testing.T) string {
	t.Helper()
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("TEST_DATABASE_URL not set, skipping integration test")
	}
	return url
}

// TestConnect_Success verifies that we can connect to a real PostgreSQL database.
//
// Go testing pattern — "happy path" test:
//   Tests the normal, expected behavior. The name convention is TestFunctionName_Scenario.
//   Laravel equivalent: /** @test */ public function it_connects_successfully()
//   Django equivalent:  def test_connect_success(self)
//
// Go concept — defer db.Close():
//   defer schedules a function call to run when the surrounding function returns.
//   This ensures the DB connection is always cleaned up, even if the test fails.
//   Like PHP's try/finally or Python's with statement / context manager.
func TestConnect_Success(t *testing.T) {
	url := getTestDatabaseURL(t)

	db, err := Connect(url)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	defer db.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		t.Fatalf("expected ping to succeed, got %v", err)
	}
}

// TestConnect_InvalidURL verifies that connecting to a bad URL returns an error.
//
// Go testing pattern — "error path" test:
//   Tests that the function handles bad input gracefully. In Go, we check that
//   err != nil (rather than expecting exceptions like in PHP/Python).
//
//   Go has no exceptions — errors are returned as values. This means every test
//   must explicitly check the error return value rather than wrapping in
//   try/catch (PHP) or with self.assertRaises (Django/pytest).
func TestConnect_InvalidURL(t *testing.T) {
	_, err := Connect("postgres://invalid:invalid@localhost:9999/nonexistent?sslmode=disable&connect_timeout=1")
	if err == nil {
		t.Fatal("expected error for invalid connection, got nil")
	}
}
