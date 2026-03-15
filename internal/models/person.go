// Package models — person.go defines the Person model for loan/debt tracking.
//
// A Person represents someone you lend money to or borrow money from.
// When a transaction of type "loan_out", "loan_in", or "loan_repayment" is created,
// it references a PersonID, and the Person's NetBalance is updated accordingly.
//
// Laravel analogy: Like a Contact Eloquent model with a cached balance computed from
// related transactions. In Laravel, you might use a hasMany relationship and
// sum('amount'), but here we cache the running total for performance.
//
// Django analogy: Similar to a Model with a DecimalField for net_balance that acts
// as a denormalized aggregate — updated via signals or service-layer logic rather
// than computed on every request.
package models

import "time"

// Person tracks someone you lend money to or borrow from.
//
// NetBalance is a cached running total (denormalized for performance):
//   - Positive = they owe you money (you lent to them via loan_out)
//   - Negative = you owe them money (you borrowed via loan_in)
//   - Zero = all debts are settled
//
// The balance is updated atomically in the service layer whenever a loan or
// repayment transaction is created. This avoids expensive SUM queries on every
// page load (similar to Laravel's withCount/withSum pattern, but pre-computed).
type Person struct {
	ID            string    `json:"id" db:"id"`
	Name          string    `json:"name" db:"name"`
	Note          *string   `json:"note,omitempty" db:"note"`                   // *string = nullable; nil maps to SQL NULL. In Laravel: $table->string('note')->nullable(). In Django: CharField(null=True, blank=True)
	NetBalance    float64   `json:"net_balance" db:"net_balance"`               // legacy sum of both currencies — kept for backward compat
	NetBalanceEGP float64   `json:"net_balance_egp" db:"net_balance_egp"`       // EGP-denominated debt balance
	NetBalanceUSD float64   `json:"net_balance_usd" db:"net_balance_usd"`       // USD-denominated debt balance
	CreatedAt     time.Time `json:"created_at" db:"created_at"`
	UpdatedAt     time.Time `json:"updated_at" db:"updated_at"`
}
