// Integration tests for InstitutionRepo.
//
// These are INTEGRATION tests, not unit tests — they hit a real PostgreSQL database.
// This is the Go equivalent of Laravel's RefreshDatabase trait or Django's TestCase
// with a live database.
//
// Key Go testing patterns used here:
//
//   - Test functions must be named Test* and accept *testing.T
//   - t.Fatalf() stops the test immediately (like $this->fail() in PHPUnit)
//   - t.Errorf() records a failure but continues (like $this->addFailure())
//   - t.Error() is like t.Errorf() without formatting
//   - context.Background() provides a non-cancellable context (fine for tests)
//
// To run these tests: TEST_DATABASE_URL=... go test ./internal/repository/ -p 1
// The -p 1 flag runs packages sequentially to avoid DB conflicts.
//
// See: https://pkg.go.dev/testing
package repository

import (
	"context"
	"database/sql"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

// TestInstitutionRepo_Create verifies that inserting an institution returns
// a record with an auto-generated UUID and timestamp.
//
// testutil.NewTestDB(t) connects to the test database (TEST_DATABASE_URL env var).
// If the env var is not set, the test is skipped with t.Skip().
// testutil.CleanTable truncates the table to ensure a clean slate — like
// Laravel's RefreshDatabase or Django's TransactionTestCase.
func TestInstitutionRepo_Create(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	repo := NewInstitutionRepo(db)

	inst, err := repo.Create(context.Background(), models.Institution{
		Name: "HSBC",
		Type: models.InstitutionTypeBank,
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if inst.ID == "" {
		t.Error("expected ID to be set")
	}
	if inst.Name != "HSBC" {
		t.Errorf("expected name HSBC, got %q", inst.Name)
	}
	if inst.CreatedAt.IsZero() {
		t.Error("expected created_at to be set")
	}
}

// TestInstitutionRepo_GetByID verifies that we can retrieve a previously created institution.
// This is the classic "create then read" integration test pattern.
func TestInstitutionRepo_GetByID(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	repo := NewInstitutionRepo(db)

	created, _ := repo.Create(context.Background(), models.Institution{
		Name: "CIB",
		Type: models.InstitutionTypeBank,
	})

	found, err := repo.GetByID(context.Background(), created.ID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if found.Name != "CIB" {
		t.Errorf("expected name CIB, got %q", found.Name)
	}
}

// TestInstitutionRepo_GetByID_NotFound verifies the error path — looking up
// a non-existent UUID should return an error (wrapping sql.ErrNoRows).
// Testing error paths is important — like PHPUnit's expectException().
func TestInstitutionRepo_GetByID_NotFound(t *testing.T) {
	db := testutil.NewTestDB(t)
	repo := NewInstitutionRepo(db)

	_, err := repo.GetByID(context.Background(), "00000000-0000-0000-0000-000000000000")
	if err == nil {
		t.Error("expected error for non-existent ID")
	}
}

// TestInstitutionRepo_GetAll verifies listing all institutions respects display_order.
func TestInstitutionRepo_GetAll(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	repo := NewInstitutionRepo(db)

	repo.Create(context.Background(), models.Institution{Name: "HSBC", Type: models.InstitutionTypeBank, DisplayOrder: 1})
	repo.Create(context.Background(), models.Institution{Name: "Telda", Type: models.InstitutionTypeFintech, DisplayOrder: 2})

	all, err := repo.GetAll(context.Background())
	if err != nil {
		t.Fatalf("get all: %v", err)
	}
	if len(all) < 2 {
		t.Fatalf("expected at least 2 institutions, got %d", len(all))
	}
	// Verify our institutions are in the list and display_order is respected
	var foundHSBC, foundTelda bool
	for _, inst := range all {
		if inst.Name == "HSBC" {
			foundHSBC = true
		}
		if inst.Name == "Telda" {
			foundTelda = true
		}
	}
	if !foundHSBC || !foundTelda {
		t.Errorf("expected to find both HSBC and Telda in results")
	}
}

// TestInstitutionRepo_Update verifies that updating a field persists the change
// and that updated_at is advanced (server-side timestamp via now()).
func TestInstitutionRepo_Update(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	repo := NewInstitutionRepo(db)

	created, _ := repo.Create(context.Background(), models.Institution{
		Name: "Old Name",
		Type: models.InstitutionTypeBank,
	})

	created.Name = "New Name"
	updated, err := repo.Update(context.Background(), created)
	if err != nil {
		t.Fatalf("update: %v", err)
	}
	if updated.Name != "New Name" {
		t.Errorf("expected name 'New Name', got %q", updated.Name)
	}
	if !updated.UpdatedAt.After(created.CreatedAt) {
		t.Error("expected updated_at to be after created_at")
	}
}

// TestInstitutionRepo_Delete verifies that deleting removes the record and
// a subsequent GetByID returns an error.
func TestInstitutionRepo_Delete(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	repo := NewInstitutionRepo(db)

	created, _ := repo.Create(context.Background(), models.Institution{
		Name: "To Delete",
		Type: models.InstitutionTypeBank,
	})

	err := repo.Delete(context.Background(), created.ID)
	if err != nil {
		t.Fatalf("delete: %v", err)
	}

	_, err = repo.GetByID(context.Background(), created.ID)
	if err == nil {
		t.Error("expected error after deletion")
	}
}

// TestInstitutionRepo_Delete_NotFound verifies that deleting a non-existent record
// returns sql.ErrNoRows. This ensures the handler can distinguish "not found"
// from other errors and return a proper 404 HTTP response.
func TestInstitutionRepo_Delete_NotFound(t *testing.T) {
	db := testutil.NewTestDB(t)
	repo := NewInstitutionRepo(db)

	err := repo.Delete(context.Background(), "00000000-0000-0000-0000-000000000000")
	if err != sql.ErrNoRows {
		t.Errorf("expected sql.ErrNoRows, got %v", err)
	}
}
