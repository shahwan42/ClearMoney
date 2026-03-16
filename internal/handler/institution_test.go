// institution_test.go — Integration tests for institution CRUD API.
//
// These tests exercise the full stack: HTTP request -> router -> middleware -> handler
// -> service -> repository -> real PostgreSQL database.
//
// Integration test patterns used here:
//
//   testutil.NewTestDB(t): Opens a connection to the test database using TEST_DATABASE_URL.
//     Tests are skipped if the env var is not set (allows running without a DB).
//     Like Laravel's RefreshDatabase trait that uses a test database.
//
//   testutil.CleanTable(t, db, "institutions"): Truncates the table before each test.
//     Like Laravel's DatabaseTransactions trait or Django's TransactionTestCase.
//
//   testRouter(t, db): Creates a full router with auth pre-configured (see test_helpers_test.go).
//     Returns the router, an addAuth function, and the authenticated userID.
//     This avoids repeating auth setup in every test.
//
//   testutil.CreateInstitution(t, db, ...): Factory helper that inserts a test record.
//     Like Laravel's factory(Institution::class)->create() or Django's baker.make().
//
// Test structure follows the Arrange-Act-Assert pattern:
//   1. Arrange: Set up test data (create institutions, accounts)
//   2. Act: Make the HTTP request
//   3. Assert: Check the response status, body, and side effects
//
// See: https://pkg.go.dev/net/http/httptest
package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/testutil"
)

func TestInstitutionHandler_CreateAndList(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router, addAuth, _ := testRouter(t, db)

	// POST — create an institution
	body := `{"name":"HSBC","type":"bank"}`
	req := httptest.NewRequest(http.MethodPost, "/api/institutions", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
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
	addAuth(req)
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
	router, addAuth, userID := testRouter(t, db)

	// Create first
	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "CIB", UserID: userID})

	// GET by ID
	req := httptest.NewRequest(http.MethodGet, "/api/institutions/"+inst.ID, nil)
	addAuth(req)
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
	router, addAuth, _ := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/api/institutions/00000000-0000-0000-0000-000000000000", nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", w.Code)
	}
}

func TestInstitutionHandler_Update(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router, addAuth, userID := testRouter(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "Old", UserID: userID})

	body := `{"name":"New Name","type":"fintech"}`
	req := httptest.NewRequest(http.MethodPut, "/api/institutions/"+inst.ID, bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
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
	router, addAuth, userID := testRouter(t, db)

	inst := testutil.CreateInstitution(t, db, models.Institution{Name: "To Delete", UserID: userID})

	req := httptest.NewRequest(http.MethodDelete, "/api/institutions/"+inst.ID, nil)
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusNoContent {
		t.Errorf("delete: expected 204, got %d", w.Code)
	}

	// Verify it's gone
	req = httptest.NewRequest(http.MethodGet, "/api/institutions/"+inst.ID, nil)
	addAuth(req)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("after delete: expected 404, got %d", w.Code)
	}
}

func TestInstitutionHandler_Create_EmptyName(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth, _ := testRouter(t, db)

	body := `{"name":"","type":"bank"}`
	req := httptest.NewRequest(http.MethodPost, "/api/institutions", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for empty name, got %d", w.Code)
	}
}

func TestInstitutionHandler_Create_InvalidJSON(t *testing.T) {
	db := testutil.NewTestDB(t)
	router, addAuth, _ := testRouter(t, db)

	req := httptest.NewRequest(http.MethodPost, "/api/institutions", bytes.NewBufferString("not json"))
	req.Header.Set("Content-Type", "application/json")
	addAuth(req)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for invalid JSON, got %d", w.Code)
	}
}

// TestInstitutionHandler_ListEmpty verifies that listing with no data returns []
// (empty JSON array) instead of null. This is important for frontend JSON parsing.
func TestInstitutionHandler_ListEmpty(t *testing.T) {
	db := testutil.NewTestDB(t)
	testutil.CleanTable(t, db, "institutions")
	router, addAuth, _ := testRouter(t, db)

	req := httptest.NewRequest(http.MethodGet, "/api/institutions", nil)
	addAuth(req)
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
