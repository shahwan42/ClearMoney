package models

import "time"

type Person struct {
	ID         string    `json:"id" db:"id"`
	Name       string    `json:"name" db:"name"`
	Note       *string   `json:"note,omitempty" db:"note"`
	NetBalance float64   `json:"net_balance" db:"net_balance"`
	CreatedAt  time.Time `json:"created_at" db:"created_at"`
	UpdatedAt  time.Time `json:"updated_at" db:"updated_at"`
}
