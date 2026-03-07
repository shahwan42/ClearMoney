package models

import "time"

// CategoryType is a string enum — expense or income.
// Like Laravel's string-backed enums or Django's TextChoices.
type CategoryType string

const (
	CategoryTypeExpense CategoryType = "expense"
	CategoryTypeIncome  CategoryType = "income"
)

// Category groups transactions by purpose (e.g., "Groceries", "Salary").
// Similar to a Category model in Laravel/Django with soft-archive support.
type Category struct {
	ID           string       `json:"id" db:"id"`
	Name         string       `json:"name" db:"name"`
	Type         CategoryType `json:"type" db:"type"`            // expense or income — determines which transaction types can use it
	Icon         *string      `json:"icon,omitempty" db:"icon"`  // *string = nullable; nil means no icon set (SQL NULL)
	IsSystem     bool         `json:"is_system" db:"is_system"`  // seeded categories that can't be deleted (like Laravel's is_default)
	IsArchived   bool         `json:"is_archived" db:"is_archived"` // soft-archive: hidden from dropdowns but kept for history
	DisplayOrder int          `json:"display_order" db:"display_order"`
	CreatedAt    time.Time    `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time    `json:"updated_at" db:"updated_at"`
}
