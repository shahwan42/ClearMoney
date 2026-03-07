package models

import "time"

// Person tracks someone you lend money to or borrow from.
// Think of it like a Contact model in Laravel/Django — used for loan tracking.
//
// NetBalance is a running total:
//   - Positive = they owe you money (you lent to them)
//   - Negative = you owe them money (you borrowed from them)
type Person struct {
	ID         string    `json:"id" db:"id"`
	Name       string    `json:"name" db:"name"`
	Note       *string   `json:"note,omitempty" db:"note"` // *string = nullable; nil maps to SQL NULL (like nullable() in Laravel migrations)
	NetBalance float64   `json:"net_balance" db:"net_balance"` // cached running total, updated on each loan/repayment transaction
	CreatedAt  time.Time `json:"created_at" db:"created_at"`
	UpdatedAt  time.Time `json:"updated_at" db:"updated_at"`
}
