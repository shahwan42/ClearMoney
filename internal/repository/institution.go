// Package repository implements the data access layer (DAL).
//
// This is equivalent to Laravel's Eloquent repositories or Django's QuerySets/Managers.
// Each file handles queries for one domain entity. Repositories accept a *sql.DB
// and return domain models — they don't contain business logic, just SQL.
//
// In Go, we don't have an ORM like Eloquent or Django ORM. Instead, we write
// SQL directly and scan results into structs. This is more verbose but gives
// full control over queries and avoids the N+1 problem by design.
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// InstitutionRepo handles all database operations for institutions.
// It holds a reference to the database connection pool (*sql.DB).
//
// This pattern is similar to a Laravel repository class:
//
//	class InstitutionRepository {
//	    public function __construct(private DB $db) {}
//	}
type InstitutionRepo struct {
	db *sql.DB
}

// NewInstitutionRepo creates a new repository instance.
// In Laravel terms, this is what the service container does when resolving dependencies.
func NewInstitutionRepo(db *sql.DB) *InstitutionRepo {
	return &InstitutionRepo{db: db}
}

// Create inserts a new institution and returns it with its generated ID.
// Uses RETURNING to get the auto-generated fields in a single query
// (PostgreSQL feature — no need for a separate SELECT after INSERT).
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
// Returns sql.ErrNoRows if not found (similar to Laravel's findOrFail).
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
// Similar to Institution::orderBy('display_order')->get() in Laravel.
func (r *InstitutionRepo) GetAll(ctx context.Context) ([]models.Institution, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, name, type, color, icon, display_order, created_at, updated_at
		FROM institutions ORDER BY display_order, name
	`)
	if err != nil {
		return nil, fmt.Errorf("listing institutions: %w", err)
	}
	defer rows.Close() // Always close rows to release the DB connection back to the pool

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

	// rows.Err() catches errors that occurred during iteration
	// (e.g., connection dropped mid-query)
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterating institutions: %w", err)
	}

	return institutions, nil
}

// Update modifies an existing institution's fields.
// Returns the updated institution. Fails if the ID doesn't exist.
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
func (r *InstitutionRepo) UpdateDisplayOrder(ctx context.Context, id string, order int) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE institutions SET display_order = $2, updated_at = now() WHERE id = $1
	`, id, order)
	return err
}

// Delete removes an institution by ID.
// Due to CASCADE on the accounts FK, this also deletes all accounts under it.
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
