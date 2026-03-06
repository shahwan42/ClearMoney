package models

import "time"

type InstitutionType string

const (
	InstitutionTypeBank    InstitutionType = "bank"
	InstitutionTypeFintech InstitutionType = "fintech"
)

type Institution struct {
	ID           string          `json:"id" db:"id"`
	Name         string          `json:"name" db:"name"`
	Type         InstitutionType `json:"type" db:"type"`
	Color        *string         `json:"color,omitempty" db:"color"`
	Icon         *string         `json:"icon,omitempty" db:"icon"`
	DisplayOrder int             `json:"display_order" db:"display_order"`
	CreatedAt    time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time       `json:"updated_at" db:"updated_at"`
}
