// Package repository implements the data access layer (DAL).
//
// Laravel analogy:  This package is like your app/Repositories/ directory or
//                   Eloquent model query scopes — all database reads/writes live here.
// Django analogy:   This is like models.py Managers and QuerySets — the methods that
//                   actually touch the database.
//
// Each file handles queries for one domain entity. Repositories accept a *sql.DB
// and return domain models — they don't contain business logic, just SQL.
//
// In Go, we don't have an ORM like Eloquent or Django ORM. Instead, we write
// raw SQL and scan results into structs. This is more verbose but gives
// full control over queries and avoids the N+1 problem by design.
//
// Key patterns used throughout this package:
//
//   - *sql.DB is a connection POOL, not a single connection.
//     Think of it like Laravel's DB facade or Django's django.db.connection.
//     It's safe to share across goroutines (like PHP-FPM workers).
//     See: https://pkg.go.dev/database/sql#DB
//
//   - QueryRowContext: executes a query expected to return ONE row (like ->first()).
//     See: https://pkg.go.dev/database/sql#DB.QueryRowContext
//
//   - QueryContext: executes a query that returns MANY rows (like ->get()).
//     You MUST call rows.Close() when done (use defer).
//     See: https://pkg.go.dev/database/sql#DB.QueryContext
//
//   - ExecContext: executes a query that doesn't return rows (UPDATE, DELETE).
//     Returns a sql.Result with RowsAffected() and LastInsertId().
//     See: https://pkg.go.dev/database/sql#DB.ExecContext
//
//   - Scan(&field1, &field2, ...): reads column values into Go variables.
//     The & operator passes a pointer so the function can write into our variable.
//     Like $stmt->fetch(PDO::FETCH_INTO) or Django's .values_list().
//     See: https://pkg.go.dev/database/sql#Row.Scan
//
//   - context.Context (ctx): carries request-scoped deadlines and cancellation.
//     If the HTTP request is cancelled, the DB query gets cancelled too.
//     Like Laravel's request lifecycle or Django's middleware chain.
//     See: https://pkg.go.dev/context
//
//   - Error handling: Go returns errors as values, no exceptions/try-catch.
//     fmt.Errorf("...: %w", err) wraps errors to preserve the chain (like
//     Laravel's report() or Python's raise ... from err).
//     See: https://pkg.go.dev/fmt#Errorf
//
//   - sql.ErrNoRows: returned when QueryRow finds no matching row.
//     Equivalent to ModelNotFoundException in Laravel or DoesNotExist in Django.
//     See: https://pkg.go.dev/database/sql#pkg-variables
//
//   - PostgreSQL $1, $2, ...: parameterized placeholders preventing SQL injection.
//     Laravel uses ?, Django uses %s — PostgreSQL uses numbered placeholders.
//
//   - RETURNING clause: PostgreSQL-specific — returns values from INSERT/UPDATE
//     in a single query. No need for a separate SELECT after INSERT.
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/shahwan42/clearmoney/internal/models"
)

// InstitutionRepo handles all database operations for the institutions table.
// It holds a reference to the database connection pool (*sql.DB).
//
// This struct-with-db pattern is Go's version of dependency injection:
//
//   Laravel:  class InstitutionRepository { public function __construct(private DB $db) {} }
//   Django:   class InstitutionManager(models.Manager): ...  (uses self.model._default_manager)
//   Go:       type InstitutionRepo struct { db *sql.DB }     (explicit DB reference)
//
// *sql.DB is NOT a single connection — it's a connection pool that manages
// opening/closing connections automatically. You never need to worry about
// connection exhaustion like you might with raw PDO in PHP.
// See: https://pkg.go.dev/database/sql#DB
type InstitutionRepo struct {
	db *sql.DB
}

// NewInstitutionRepo creates a new repository instance (constructor function).
//
// In Laravel, the service container auto-resolves dependencies:
//   $this->app->bind(InstitutionRepo::class, fn($app) => new InstitutionRepo($app->make('db')));
// In Django, managers are attached automatically via metaclass magic.
// In Go, we explicitly pass dependencies — this is manual dependency injection.
// It's more verbose but makes the dependency graph crystal clear.
func NewInstitutionRepo(db *sql.DB) *InstitutionRepo {
	return &InstitutionRepo{db: db}
}

// Create inserts a new institution and returns it with its generated ID.
//
// QueryRowContext is used because we expect exactly ONE row back (via RETURNING).
//   - Laravel equivalent: Institution::create([...]); // Eloquent auto-fills id, timestamps
//   - Django equivalent:  Institution.objects.create(...)
//
// The RETURNING clause is a PostgreSQL feature that returns column values from the
// newly inserted row in the same query. Without it, you'd need a separate SELECT
// to get the auto-generated id, created_at, and updated_at.
//
// $1, $2, ... are PostgreSQL parameterized placeholders. They prevent SQL injection
// (like PDO's prepared statements or Django's parameterized queries).
// The values are passed as extra arguments after the SQL string.
//
// .Scan(&inst.ID, ...) reads the RETURNING values into the struct fields.
// The & means "pointer to" — Scan writes directly into our variables.
//
// fmt.Errorf("...: %w", err) wraps the error with context while preserving the
// original error. The %w verb enables errors.Is() / errors.As() checks up the chain.
// See: https://pkg.go.dev/fmt#Errorf
func (r *InstitutionRepo) Create(ctx context.Context, inst models.Institution) (models.Institution, error) {
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO institutions (name, type, color, icon, display_order)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, created_at, updated_at
	`, inst.Name, inst.Type, inst.Color, inst.Icon, inst.DisplayOrder,
	).Scan(&inst.ID, &inst.CreatedAt, &inst.UpdatedAt)

	if err != nil {
		return models.Institution{}, fmt.Errorf("inserting institution: %w", err)
	}
	return inst, nil
}

// GetByID retrieves a single institution by its UUID.
//
// Returns sql.ErrNoRows (wrapped) if not found.
//   - Laravel:  Institution::findOrFail($id)  → throws ModelNotFoundException
//   - Django:   Institution.objects.get(id=id) → raises DoesNotExist
//   - Go:       sql.ErrNoRows is returned as an error value (no exceptions in Go)
//
// You can check for "not found" upstream with: errors.Is(err, sql.ErrNoRows)
// See: https://pkg.go.dev/database/sql#pkg-variables
func (r *InstitutionRepo) GetByID(ctx context.Context, id string) (models.Institution, error) {
	var inst models.Institution
	err := r.db.QueryRowContext(ctx, `
		SELECT id, name, type, color, icon, display_order, created_at, updated_at
		FROM institutions WHERE id = $1
	`, id).Scan(
		&inst.ID, &inst.Name, &inst.Type, &inst.Color, &inst.Icon,
		&inst.DisplayOrder, &inst.CreatedAt, &inst.UpdatedAt,
	)
	if err != nil {
		return models.Institution{}, fmt.Errorf("getting institution: %w", err)
	}
	return inst, nil
}

// GetAll retrieves all institutions ordered by display_order.
//
//   Laravel:  Institution::orderBy('display_order')->orderBy('name')->get()
//   Django:   Institution.objects.order_by('display_order', 'name')
//
// QueryContext (not QueryRowContext) is used when we expect MULTIPLE rows.
// It returns *sql.Rows — an iterator you loop over with rows.Next().
// See: https://pkg.go.dev/database/sql#DB.QueryContext
//
// The query-scan-loop pattern is the Go equivalent of Eloquent's ->get():
//   1. QueryContext — execute the query, get a rows cursor
//   2. defer rows.Close() — ALWAYS close to return the connection to the pool
//   3. for rows.Next() — iterate like a PHP foreach or Python for-in
//   4. rows.Scan(&...) — read each row's columns into a struct
//   5. rows.Err() — check for errors that happened DURING iteration
func (r *InstitutionRepo) GetAll(ctx context.Context) ([]models.Institution, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, name, type, color, icon, display_order, created_at, updated_at
		FROM institutions ORDER BY display_order, name
	`)
	if err != nil {
		return nil, fmt.Errorf("listing institutions: %w", err)
	}
	// defer rows.Close() ensures the DB connection is returned to the pool
	// even if we return early due to an error. Like a finally{} block in PHP
	// or a context manager (with statement) in Python.
	defer rows.Close()

	// var institutions []models.Institution declares a nil slice (like an empty array).
	// append() will allocate memory as needed — no need to pre-size.
	var institutions []models.Institution
	for rows.Next() {
		var inst models.Institution
		if err := rows.Scan(
			&inst.ID, &inst.Name, &inst.Type, &inst.Color, &inst.Icon,
			&inst.DisplayOrder, &inst.CreatedAt, &inst.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("scanning institution: %w", err)
		}
		institutions = append(institutions, inst)
	}

	// rows.Err() catches errors that occurred DURING iteration
	// (e.g., connection dropped mid-query, encoding error on a later row).
	// rows.Next() returns false on error but doesn't tell you why — Err() does.
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterating institutions: %w", err)
	}

	return institutions, nil
}

// Update modifies an existing institution's fields.
// Returns the updated institution with the refreshed updated_at timestamp.
//
// Uses RETURNING updated_at to get the server-set timestamp in the same query.
//   Laravel:  $inst->update([...]); // Eloquent auto-updates updated_at
//   Django:   inst.save(update_fields=[...]) // Django auto-updates auto_now fields
//
// Fails with sql.ErrNoRows (wrapped) if the ID doesn't exist in the table.
func (r *InstitutionRepo) Update(ctx context.Context, inst models.Institution) (models.Institution, error) {
	err := r.db.QueryRowContext(ctx, `
		UPDATE institutions
		SET name = $2, type = $3, color = $4, icon = $5, display_order = $6, updated_at = now()
		WHERE id = $1
		RETURNING updated_at
	`, inst.ID, inst.Name, inst.Type, inst.Color, inst.Icon, inst.DisplayOrder,
	).Scan(&inst.UpdatedAt)

	if err != nil {
		return models.Institution{}, fmt.Errorf("updating institution: %w", err)
	}
	return inst, nil
}

// UpdateDisplayOrder sets the display_order for an institution.
//
// ExecContext is used (instead of QueryRowContext) because we don't need any
// data back from the query — just "did it work?". It returns sql.Result but
// we only need the error. The _ discards the result.
//
//   Laravel:  Institution::where('id', $id)->update(['display_order' => $order]);
//   Django:   Institution.objects.filter(id=id).update(display_order=order)
//
// See: https://pkg.go.dev/database/sql#DB.ExecContext
func (r *InstitutionRepo) UpdateDisplayOrder(ctx context.Context, id string, order int) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE institutions SET display_order = $2, updated_at = now() WHERE id = $1
	`, id, order)
	return err
}

// Delete removes an institution by ID.
// Due to CASCADE on the accounts FK, this also deletes all accounts under it.
//
// This method demonstrates the ExecContext + RowsAffected pattern:
//   1. ExecContext runs the DELETE — returns sql.Result (not rows)
//   2. result.RowsAffected() tells us if any row was actually deleted
//   3. If 0 rows affected → return sql.ErrNoRows (the record didn't exist)
//
// This is like:
//   Laravel:  $deleted = Institution::destroy($id); if ($deleted === 0) throw ...
//   Django:   count, _ = Institution.objects.filter(id=id).delete(); if count == 0: raise ...
//
// See: https://pkg.go.dev/database/sql#Result
func (r *InstitutionRepo) Delete(ctx context.Context, id string) error {
	result, err := r.db.ExecContext(ctx, `DELETE FROM institutions WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("deleting institution: %w", err)
	}

	// RowsAffected tells us if the DELETE actually found a row.
	// Similar to checking $deleted > 0 in Laravel.
	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("checking rows affected: %w", err)
	}
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}
