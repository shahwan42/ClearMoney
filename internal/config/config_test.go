// Go Testing Patterns — A Guide for PHP/Python Developers
//
// Go's testing is built into the language: `go test ./...` runs all tests.
// No need for PHPUnit, pytest, or a separate test runner — it's all stdlib.
//
// Key differences from PHPUnit/pytest:
//
//  1. Test file naming: *_test.go (not tests/ directory like Laravel or test_*.py like Django).
//     Test files live NEXT TO the code they test, in the same package.
//
//  2. Test function naming: must start with Test and accept *testing.T.
//     PHPUnit: public function testLoadDefaults(): void { ... }
//     pytest:  def test_load_defaults(): ...
//     Go:      func TestLoad_Defaults(t *testing.T) { ... }
//
//  3. No assertions library by default. Instead of $this->assertEquals() or assert ==,
//     you use if-checks and call t.Errorf() to report failures. t.Errorf does NOT
//     stop the test — it marks it as failed but continues (like PHPUnit's assertSoftly).
//     Use t.Fatalf() to stop immediately (like PHPUnit's default behavior).
//
//  4. Package access: test files in `package config` (not `package config_test`) have
//     access to unexported (lowercase) functions. This is "white-box" testing.
//     Using `package config_test` would be "black-box" testing (only exported API).
//
//  5. No setUp/tearDown methods. Use defer for cleanup, or t.Cleanup() for teardown.
//     The defer keyword here acts like PHPUnit's tearDown() or pytest's yield fixture.
//
// Run these tests: `go test ./internal/config/`
// Run with verbose output: `go test -v ./internal/config/`
// Run a single test: `go test -run TestLoad_Defaults ./internal/config/`
//
// See: https://pkg.go.dev/testing — Go's testing package documentation
// See: https://go.dev/doc/tutorial/add-a-test — official testing tutorial
package config

import (
	"os"
	"testing"
)

// TestLoad_Defaults verifies that Load() returns sensible defaults when
// no environment variables are set.
//
// This is a "unit test" — it tests one function with controlled inputs.
// The naming convention is TestFunctionName_Scenario (underscores for readability).
func TestLoad_Defaults(t *testing.T) {
	// Unset any env vars that might interfere.
	// Unlike PHPUnit where each test gets a fresh process, Go tests share the
	// same process. Environment variable changes in one test affect others,
	// so we must clean up (see defer in TestLoad_FromEnv below).
	os.Unsetenv("PORT")
	os.Unsetenv("DATABASE_URL")
	os.Unsetenv("ENV")

	cfg := Load()

	// t.Errorf marks the test as failed but continues executing.
	// This is like PHPUnit's expectation chaining — you see ALL failures at once,
	// not just the first one. Format string uses %s for strings, %d for ints, etc.
	// Compare:
	//   PHPUnit: $this->assertEquals("8080", $cfg->port);
	//   pytest:  assert cfg.port == "8080"
	//   Go:      if cfg.Port != "8080" { t.Errorf("expected ..., got %s", cfg.Port) }
	if cfg.Port != "8080" {
		t.Errorf("expected default port 8080, got %s", cfg.Port)
	}
	if cfg.Env != "development" {
		t.Errorf("expected default env development, got %s", cfg.Env)
	}
	if cfg.DatabaseURL != "" {
		t.Errorf("expected empty database URL by default, got %s", cfg.DatabaseURL)
	}
}

// TestLoad_FromEnv verifies that Load() reads values from environment variables.
func TestLoad_FromEnv(t *testing.T) {
	// Set up test fixtures (environment variables).
	os.Setenv("PORT", "9090")
	os.Setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/clearmoney")
	os.Setenv("ENV", "production")
	// defer runs this cleanup function when TestLoad_FromEnv returns.
	// This is Go's equivalent of PHPUnit's tearDown() or pytest's fixture cleanup.
	// The anonymous func() { ... }() pattern is an "immediately invoked function
	// expression" (IIFE) — similar to JavaScript's (function() { ... })().
	// We wrap multiple statements in a closure because defer takes a single function call.
	defer func() {
		os.Unsetenv("PORT")
		os.Unsetenv("DATABASE_URL")
		os.Unsetenv("ENV")
	}()

	cfg := Load()

	if cfg.Port != "9090" {
		t.Errorf("expected port 9090, got %s", cfg.Port)
	}
	if cfg.DatabaseURL != "postgres://user:pass@localhost:5432/clearmoney" {
		t.Errorf("expected database URL from env, got %s", cfg.DatabaseURL)
	}
	if cfg.Env != "production" {
		t.Errorf("expected env production, got %s", cfg.Env)
	}
}

// TestConfig_IsDevelopment tests a method on the Config struct.
// Note how we create a Config struct literal directly — no factory or builder needed.
// This is like: new Config(['env' => 'development']) in PHP,
// or Config(env='development') in Python.
func TestConfig_IsDevelopment(t *testing.T) {
	cfg := Config{Env: "development"}
	if !cfg.IsDevelopment() {
		t.Error("expected IsDevelopment to return true")
	}

	// We can mutate the struct directly — Go structs are mutable value types.
	cfg.Env = "production"
	if cfg.IsDevelopment() {
		t.Error("expected IsDevelopment to return false")
	}
}
