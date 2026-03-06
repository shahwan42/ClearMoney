package models

import "time"

type CategoryType string

const (
	CategoryTypeExpense CategoryType = "expense"
	CategoryTypeIncome  CategoryType = "income"
)

type Category struct {
	ID           string       `json:"id" db:"id"`
	Name         string       `json:"name" db:"name"`
	Type         CategoryType `json:"type" db:"type"`
	Icon         *string      `json:"icon,omitempty" db:"icon"`
	IsSystem     bool         `json:"is_system" db:"is_system"`
	IsArchived   bool         `json:"is_archived" db:"is_archived"`
	DisplayOrder int          `json:"display_order" db:"display_order"`
	CreatedAt    time.Time    `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time    `json:"updated_at" db:"updated_at"`
}
