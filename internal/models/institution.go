// Package models defines the domain structs shared across all layers.
// These are like Laravel's Eloquent models or Django's models.py, but in Go
// they're plain structs with no ORM magic — just data containers with tags
// that tell JSON and DB libraries how to map fields.
//
// Key Go conventions to note:
//   - Struct tags (`json:"..." db:"..."`) are metadata for serialization,
//     similar to $casts in Laravel or field options in Django.
//   - Pointer types (*string, *float64) represent nullable fields.
//     nil = SQL NULL, similar to nullable columns in Laravel migrations.
//   - Exported (capitalized) names are public; unexported are private.
package models

import "time"

// InstitutionType is a string enum for bank vs fintech.
// In Go, we define "enums" as named string types with constants.
// There's no built-in enum keyword like PHP 8.1 enums.
type InstitutionType string

const (
	InstitutionTypeBank    InstitutionType = "bank"
	InstitutionTypeFintech InstitutionType = "fintech"
)

// Institution represents a financial institution (e.g., HSBC, CIB, Telda).
// Accounts belong to institutions — this is the top-level grouping.
type Institution struct {
	ID           string          `json:"id" db:"id"`
	Name         string          `json:"name" db:"name"`
	Type         InstitutionType `json:"type" db:"type"`
	Color        *string         `json:"color,omitempty" db:"color"` // hex color for UI theming
	Icon         *string         `json:"icon,omitempty" db:"icon"`   // optional icon path
	DisplayOrder int             `json:"display_order" db:"display_order"`
	CreatedAt    time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time       `json:"updated_at" db:"updated_at"`
}
