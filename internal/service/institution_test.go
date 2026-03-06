package service

import (
	"context"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

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

func TestInstitutionService_Create_EmptyName(t *testing.T) {
	db := testutil.NewTestDB(t)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	_, err := svc.Create(context.Background(), models.Institution{Name: ""})
	if err == nil {
		t.Error("expected error for empty name")
	}
}

func TestInstitutionService_Create_WhitespaceName(t *testing.T) {
	db := testutil.NewTestDB(t)
	svc := NewInstitutionService(repository.NewInstitutionRepo(db))

	_, err := svc.Create(context.Background(), models.Institution{Name: "   "})
	if err == nil {
		t.Error("expected error for whitespace-only name")
	}
}

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
