// Package repository — category.go provides data access for expense/income categories.
//
// Categories are seeded via migration (system categories like "Food", "Salary") and
// users can create custom ones. System categories cannot be deleted, only archived
// (soft-deleted). This is similar to:
//   Laravel:  SoftDeletes trait with an is_archived boolean instead of deleted_at
//   Django:   A custom manager that filters out archived records by default
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/shahwan42/clearmoney/internal/models"
)

// CategoryRepo handles database operations for categories.
//
//	Laravel:  Category model + CategoryRepository
//	Django:   Category.objects (default manager)
type CategoryRepo struct {
	db *sql.DB
}

// NewCategoryRepo creates a new CategoryRepo with the given database connection pool.
func NewCategoryRepo(db *sql.DB) *CategoryRepo {
	return &CategoryRepo{db: db}
}

// GetAll retrieves all non-archived categories.
// The `WHERE is_archived = false` acts as a soft-delete filter.
//   Laravel:  Category::where('is_archived', false)->orderBy('type')->get()
//   Django:   Category.objects.filter(is_archived=False).order_by('type', 'display_order', 'name')
func (r *CategoryRepo) GetAll(ctx context.Context) ([]models.Category, error) {
	return r.queryCategories(ctx, `
		SELECT id, name, type, icon, is_system, is_archived, display_order, created_at, updated_at
		FROM categories WHERE is_archived = false
		ORDER BY type, display_order, name
	`)
}

// GetByType retrieves non-archived categories of a specific type (expense/income).
// catType is a typed string constant (models.CategoryType) — Go's way of doing enums.
//   Laravel:  Category::where('type', $catType)->where('is_archived', false)->get()
//   Django:   Category.objects.filter(type=cat_type, is_archived=False)
func (r *CategoryRepo) GetByType(ctx context.Context, catType models.CategoryType) ([]models.Category, error) {
	return r.queryCategories(ctx, `
		SELECT id, name, type, icon, is_system, is_archived, display_order, created_at, updated_at
		FROM categories WHERE type = $1 AND is_archived = false
		ORDER BY display_order, name
	`, catType)
}

// GetByID retrieves a single category.
func (r *CategoryRepo) GetByID(ctx context.Context, id string) (models.Category, error) {
	var cat models.Category
	err := r.db.QueryRowContext(ctx, `
		SELECT id, name, type, icon, is_system, is_archived, display_order, created_at, updated_at
		FROM categories WHERE id = $1
	`, id).Scan(
		&cat.ID, &cat.Name, &cat.Type, &cat.Icon, &cat.IsSystem,
		&cat.IsArchived, &cat.DisplayOrder, &cat.CreatedAt, &cat.UpdatedAt,
	)
	if err != nil {
		return models.Category{}, fmt.Errorf("getting category: %w", err)
	}
	return cat, nil
}

// Create inserts a new custom category.
// Note: is_system is hardcoded to false in the SQL — only migrations create system categories.
// RETURNING returns multiple auto-set columns in one round-trip to avoid a separate SELECT.
func (r *CategoryRepo) Create(ctx context.Context, cat models.Category) (models.Category, error) {
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO categories (name, type, icon, is_system, display_order)
		VALUES ($1, $2, $3, false, $4)
		RETURNING id, is_system, is_archived, created_at, updated_at
	`, cat.Name, cat.Type, cat.Icon, cat.DisplayOrder,
	).Scan(&cat.ID, &cat.IsSystem, &cat.IsArchived, &cat.CreatedAt, &cat.UpdatedAt)

	if err != nil {
		return models.Category{}, fmt.Errorf("inserting category: %w", err)
	}
	return cat, nil
}

// Update modifies a category's name, icon, and display_order.
func (r *CategoryRepo) Update(ctx context.Context, cat models.Category) (models.Category, error) {
	err := r.db.QueryRowContext(ctx, `
		UPDATE categories SET name = $2, icon = $3, display_order = $4, updated_at = now()
		WHERE id = $1
		RETURNING updated_at
	`, cat.ID, cat.Name, cat.Icon, cat.DisplayOrder,
	).Scan(&cat.UpdatedAt)
	if err != nil {
		return models.Category{}, fmt.Errorf("updating category: %w", err)
	}
	return cat, nil
}

// Archive soft-deletes a category by setting is_archived = true.
// Soft-delete keeps the data for historical transactions but hides it from the UI.
//   Laravel:  $category->update(['is_archived' => true]);  // like SoftDeletes but with a bool
//   Django:   category.is_archived = True; category.save()
func (r *CategoryRepo) Archive(ctx context.Context, id string) error {
	result, err := r.db.ExecContext(ctx, `
		UPDATE categories SET is_archived = true, updated_at = now() WHERE id = $1
	`, id)
	if err != nil {
		return fmt.Errorf("archiving category: %w", err)
	}
	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

// queryCategories is a DRY helper shared by GetAll and GetByType.
// The ...any (variadic) parameter lets us pass optional WHERE clause arguments.
// This avoids duplicating the rows.Scan() logic across multiple methods.
//   Laravel analogy:  A private scopeQuery() method on the repository
//   Django analogy:   A custom QuerySet method that chains filters
func (r *CategoryRepo) queryCategories(ctx context.Context, query string, args ...any) ([]models.Category, error) {
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("querying categories: %w", err)
	}
	defer rows.Close()

	var categories []models.Category
	for rows.Next() {
		var cat models.Category
		if err := rows.Scan(
			&cat.ID, &cat.Name, &cat.Type, &cat.Icon, &cat.IsSystem,
			&cat.IsArchived, &cat.DisplayOrder, &cat.CreatedAt, &cat.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("scanning category: %w", err)
		}
		categories = append(categories, cat)
	}
	return categories, rows.Err()
}
