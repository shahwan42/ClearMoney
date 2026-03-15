// Tests for InstitutionService — validates institution CRUD business logic.
//
// Go testing patterns for Laravel/Django developers:
//
// 1. Test functions MUST start with "Test" and accept *testing.T.
//    This is like PHPUnit's test methods or Django's test_ prefix.
//    Run with: go test ./internal/service/ -run TestInstitution -v
//
// 2. These are INTEGRATION tests — they use a real PostgreSQL database.
//    Like Laravel's RefreshDatabase trait but manual: we clean tables before each test.
//    Requires TEST_DATABASE_URL env var (skipped if unset, like PHPUnit's @requires).
//
// 3. testutil.NewTestDB(t) connects to the test DB and auto-cleans up.
//    t.Helper() marks helper functions so failures report the caller's line number
//    (like PHPUnit's expectation chain showing the test line, not the assertion line).
//
// 4. context.Background() provides a non-cancellable context.
//    In production, the HTTP request's context is used instead.
//
// See: https://pkg.go.dev/testing for Go's testing package
// See: https://go.dev/wiki/TableDrivenTests for table-driven test patterns
package service

import (
	"context"
	"testing"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

// TestInstitutionService_Create_Valid tests the happy path for creating an institution.
// Convention: TestTypeName_MethodName_Scenario. Similar to PHPUnit's test_create_valid_institution().
func TestInstitutionService_Create_Valid(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	inst, err := svc.Create(context.Background(), models.Institution{
		Name: "HSBC",
		Type: models.InstitutionTypeBank,
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if inst.ID == "" {
		t.Error("expected ID")
	}
}

// TestInstitutionService_Create_EmptyName tests validation rejects empty names.
// Go has no built-in assertion library like PHPUnit's assertNull/assertEquals.
// Instead, we use if/else with t.Error() or t.Fatal() (Fatal stops the test immediately).
func TestInstitutionService_Create_EmptyName(t *testing.T) {
	db := testutil.NewTestDB(t)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	_, err := svc.Create(context.Background(), models.Institution{Name: ""})
	if err == nil {
		t.Error("expected error for empty name")
	}
}

// TestInstitutionService_Create_WhitespaceName ensures names with only whitespace are rejected
// (the service trims names before checking, so "   " becomes "" and fails validation).
func TestInstitutionService_Create_WhitespaceName(t *testing.T) {
	db := testutil.NewTestDB(t)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	_, err := svc.Create(context.Background(), models.Institution{Name: "   "})
	if err == nil {
		t.Error("expected error for whitespace-only name")
	}
}

// TestInstitutionService_Create_InvalidType verifies enum-like type validation.
// Go doesn't have enums — we use string constants (models.InstitutionTypeBank = "bank").
// The service layer enforces valid values manually, unlike Laravel's Rule::in([...]).
func TestInstitutionService_Create_InvalidType(t *testing.T) {
	db := testutil.NewTestDB(t)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	_, err := svc.Create(context.Background(), models.Institution{
		Name: "Test",
		Type: "invalid",
	})
	if err == nil {
		t.Error("expected error for invalid type")
	}
}

// TestInstitutionService_Create_DefaultsToBank verifies the service applies default values.
// In Laravel, defaults go in the migration or model's $attributes array.
// In Go, we apply defaults in the service layer before passing to the repo.
func TestInstitutionService_Create_DefaultsToBank(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	inst, err := svc.Create(context.Background(), models.Institution{Name: "Test"})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if inst.Type != models.InstitutionTypeBank {
		t.Errorf("expected type bank, got %q", inst.Type)
	}
}

// TestInstitutionService_Create_Wallet verifies wallet-type institutions can be created.
func TestInstitutionService_Create_Wallet(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	inst, err := svc.Create(context.Background(), models.Institution{
		Name: "Cash",
		Type: models.InstitutionTypeWallet,
	})
	if err != nil {
		t.Fatalf("create wallet institution: %v", err)
	}
	if inst.ID == "" {
		t.Error("expected ID")
	}
	if inst.Type != models.InstitutionTypeWallet {
		t.Errorf("expected type wallet, got %q", inst.Type)
	}
}
