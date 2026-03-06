package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/testutil"
)

func TestInstitutionHandler_CreateAndList(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router := NewRouter(db)

	// POST — create an institution
	body := `{"name":"HSBC","type":"bank"}`
	req := httptest.NewRequest(http.MethodPost, "/api/institutions", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("create: expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var created models.Institution
	json.NewDecoder(w.Body).Decode(&created)
	if created.Name != "HSBC" {
		t.Errorf("expected name HSBC, got %q", created.Name)
	}
	if created.ID == "" {
		t.Error("expected ID to be set")
	}

	// GET — list all institutions
	req = httptest.NewRequest(http.MethodGet, "/api/institutions", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("list: expected 200, got %d", w.Code)
	}

	var list []models.Institution
	json.NewDecoder(w.Body).Decode(&list)
	if len(list) != 1 {
		t.Errorf("expected 1 institution, got %d", len(list))
	}
}

func TestInstitutionHandler_GetByID(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router := NewRouter(db)

	// Create first
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB"})

	// GET by ID
	req := httptest.NewRequest(http.MethodGet, "/api/institutions/"+inst.ID, nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("get: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var found models.Institution
	json.NewDecoder(w.Body).Decode(&found)
	if found.Name != "CIB" {
		t.Errorf("expected CIB, got %q", found.Name)
	}
}

func TestInstitutionHandler_GetByID_NotFound(t *testing.T) {
	db := testutil.NewTestDB(t)
	router := NewRouter(db)

	req := httptest.NewRequest(http.MethodGet, "/api/institutions/00000000-0000-0000-0000-000000000000", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", w.Code)
	}
}

func TestInstitutionHandler_Update(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router := NewRouter(db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Old"})

	body := `{"name":"New Name","type":"fintech"}`
	req := httptest.NewRequest(http.MethodPut, "/api/institutions/"+inst.ID, bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("update: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var updated models.Institution
	json.NewDecoder(w.Body).Decode(&updated)
	if updated.Name != "New Name" {
		t.Errorf("expected 'New Name', got %q", updated.Name)
	}
}

func TestInstitutionHandler_Delete(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router := NewRouter(db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "To Delete"})

	req := httptest.NewRequest(http.MethodDelete, "/api/institutions/"+inst.ID, nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusNoContent {
		t.Errorf("delete: expected 204, got %d", w.Code)
	}

	// Verify it's gone
	req = httptest.NewRequest(http.MethodGet, "/api/institutions/"+inst.ID, nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("after delete: expected 404, got %d", w.Code)
	}
}

func TestInstitutionHandler_Create_EmptyName(t *testing.T) {
	db := testutil.NewTestDB(t)
	router := NewRouter(db)

	body := `{"name":"","type":"bank"}`
	req := httptest.NewRequest(http.MethodPost, "/api/institutions", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for empty name, got %d", w.Code)
	}
}

func TestInstitutionHandler_Create_InvalidJSON(t *testing.T) {
	db := testutil.NewTestDB(t)
	router := NewRouter(db)

	req := httptest.NewRequest(http.MethodPost, "/api/institutions", bytes.NewBufferString("not json"))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for invalid JSON, got %d", w.Code)
	}
}

func TestInstitutionHandler_ListEmpty(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router := NewRouter(db)

	req := httptest.NewRequest(http.MethodGet, "/api/institutions", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	// Should return [] not null
	body := w.Body.String()
	if body != "[]\n" {
		t.Errorf("expected empty array, got %q", body)
	}
}
