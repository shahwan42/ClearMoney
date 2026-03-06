package repository

import (
	"context"
	"database/sql"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

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

func TestInstitutionRepo_GetByID_NotFound(t *testing.T) {
	db := testutil.NewTestDB(t)
	repo := NewInstitutionRepo(db)

	_, err := repo.GetByID(context.Background(), "00000000-0000-0000-0000-000000000000")
	if err == nil {
		t.Error("expected error for non-existent ID")
	}
}

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
	if len(all) != 2 {
		t.Fatalf("expected 2 institutions, got %d", len(all))
	}
	// Should be ordered by display_order
	if all[0].Name != "HSBC" {
		t.Errorf("expected first institution to be HSBC, got %q", all[0].Name)
	}
}

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

func TestInstitutionRepo_Delete_NotFound(t *testing.T) {
	db := testutil.NewTestDB(t)
	repo := NewInstitutionRepo(db)

	err := repo.Delete(context.Background(), "00000000-0000-0000-0000-000000000000")
	if err != sql.ErrNoRows {
		t.Errorf("expected sql.ErrNoRows, got %v", err)
	}
}
