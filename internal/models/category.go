// Package models — category.go defines the Category model for grouping transactions.
//
// Categories classify transactions by purpose (e.g., "Groceries", "Salary", "Rent").
// Each category is either an expense type or an income type, enforced via the
// CategoryType enum.
//
// Laravel analogy: This is like a Category Eloquent model with a type enum column.
// The IsSystem field is similar to a seeded/protected record pattern where certain
// rows (like "Salary", "Groceries") are created by migrations and cannot be deleted.
//
// Django analogy: A Model class with a TextChoices field for type and a BooleanField
// for soft-archiving. Like using is_active instead of actually deleting records.
package models

import "time"

// CategoryType is a string enum — expense or income.
//
// This restricts which transaction types can reference a category:
//   - "expense" categories can only be used with expense transactions
//   - "income" categories can only be used with income transactions
//   - Transfer/exchange transactions don't use categories at all
//
// Go enum pattern (same as InstitutionType — see institution.go for full explanation):
//   - PHP:    enum CategoryType: string { case Expense = 'expense'; ... }
//   - Django: class CategoryType(models.TextChoices): EXPENSE = 'expense', ...
type CategoryType string

const (
	CategoryTypeExpense CategoryType = "expense" // money going out (Groceries, Rent, etc.)
	CategoryTypeIncome  CategoryType = "income"  // money coming in (Salary, Freelance, etc.)
)

// Category groups transactions by purpose (e.g., "Groceries", "Salary").
//
// Soft-archive pattern: Instead of deleting categories (which would break
// historical transaction references), we set IsArchived = true. Archived
// categories are hidden from dropdown menus but still visible on existing
// transactions. This is like Laravel's SoftDeletes trait or Django's
// is_active pattern, but simpler — just a boolean flag, no deleted_at timestamp.
//
// System categories (IsSystem = true) are seeded by migrations and protected
// from deletion. Think of them like the "Uncategorized" or "Transfer" categories
// that every user needs.
type Category struct {
	ID           string       `json:"id" db:"id"`
	Name         string       `json:"name" db:"name"`
	Type         CategoryType `json:"type" db:"type"`                   // expense or income — determines which transaction types can use it
	Icon         *string      `json:"icon,omitempty" db:"icon"`         // *string = nullable; nil means no icon set (SQL NULL). In Go, a plain string defaults to "" (empty), which is different from NULL.
	IsSystem     bool         `json:"is_system" db:"is_system"`         // seeded categories that can't be deleted (like Laravel's is_default pattern)
	IsArchived   bool         `json:"is_archived" db:"is_archived"`     // soft-archive: hidden from dropdowns but kept for history (like SoftDeletes but simpler)
	DisplayOrder int          `json:"display_order" db:"display_order"` // UI ordering — lower numbers appear first
	CreatedAt    time.Time    `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time    `json:"updated_at" db:"updated_at"`
}
