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

func TestCategoryHandler_ListAll(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/api/categories", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var categories []models.Category
	json.NewDecoder(w.Body).Decode(&categories)

	// Should have at least the 25 seeded defaults (18 expense + 7 income)
	if len(categories) < 25 {
		t.Errorf("expected at least 25 categories, got %d", len(categories))
	}
}

func TestCategoryHandler_ListByType(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/api/categories?type=expense", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	var categories []models.Category
	json.NewDecoder(w.Body).Decode(&categories)

	for _, cat := range categories {
		if cat.Type != models.CategoryTypeExpense {
			t.Errorf("expected only expense categories, got %q", cat.Type)
		}
	}
	if len(categories) < 18 {
		t.Errorf("expected at least 18 expense categories, got %d", len(categories))
	}
}

func TestCategoryHandler_CreateCustom(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth := testRouter(t, db)

	body := `{"name":"Pet Expenses","type":"expense"}`
	req := httptest.NewRequest(http.MethodPost, "/api/categories", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var created models.Category
	json.NewDecoder(w.Body).Decode(&created)
	if created.IsSystem {
		t.Error("custom category should not be system")
	}
}

func TestCategoryHandler_CannotModifySystem(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth := testRouter(t, db)

	// Get a system category ID
	systemID := testutil.GetFirstCategoryID(t, db, models.CategoryTypeExpense)

	// Try to update it
	body := `{"name":"Renamed"}`
	req := httptest.NewRequest(http.MethodPut, "/api/categories/"+systemID, bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for modifying system category, got %d", w.Code)
	}

	// Try to archive it
	req = httptest.NewRequest(http.MethodDelete, "/api/categories/"+systemID, nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for archiving system category, got %d", w.Code)
	}
}
