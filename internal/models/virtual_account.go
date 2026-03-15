// Package models — virtual_account.go defines the VirtualAccount and VirtualAccountAllocation models.
//
// Virtual accounts implement "envelope budgeting" — a method where you mentally allocate
// money into different buckets (envelopes) for different purposes. The actual money
// stays in your bank accounts, but the virtual accounts track how much is earmarked
// for each goal.
//
// Users can create any number of savings goals and allocate transactions to them.
//
// Laravel analogy: VirtualAccount is an Eloquent model with a many-to-many relationship
// to Transaction via the VirtualAccountAllocation pivot table. In Laravel, you'd define this
// with belongsToMany('Transaction')->withPivot('amount')->withTimestamps().
//
// Django analogy: VirtualAccount and VirtualAccountAllocation are like a Model with a ManyToManyField
// using a custom through table. The VirtualAccountAllocation model is the "through" model that
// stores the amount allocated per transaction.
package models

import "time"

// VirtualAccount represents a user-defined savings bucket (e.g., "Emergency Fund",
// "Vacation", "New Car"). Each virtual account tracks a balance computed from
// transaction allocations.
//
// TargetAmount is *float64 (pointer to float64) — this means it's nullable.
// If the user doesn't set a savings target, TargetAmount is nil (SQL NULL).
// If they set one, it points to the target value (e.g., 500000.0 for E£500K).
//
// The difference between nil and zero matters:
//   - nil (*float64 = nil):  "no target set" — UI shows no progress bar
//   - zero (*float64 -> 0):  "target is zero" — unusual but technically valid
//   - In PHP: null vs 0. In Python: None vs 0.
type VirtualAccount struct {
	ID             string    `json:"id" db:"id"`
	Name           string    `json:"name" db:"name"`
	TargetAmount   *float64  `json:"target_amount" db:"target_amount"`     // *float64 = nullable; nil means "open-ended virtual account with no target"
	CurrentBalance float64   `json:"current_balance" db:"current_balance"` // cached sum of all allocations (denormalized for performance)
	Icon           string    `json:"icon" db:"icon"`                       // emoji or icon identifier for UI display
	Color          string    `json:"color" db:"color"`                     // hex color for progress bar and card styling
	IsArchived     bool      `json:"is_archived" db:"is_archived"`         // soft-archive: hidden from active list but kept for history
	DisplayOrder   int       `json:"display_order" db:"display_order"`     // UI ordering — lower numbers appear first
	AccountID      *string   `json:"account_id" db:"account_id"`           // linked bank account — nullable for legacy VAs
	CreatedAt      time.Time `json:"created_at" db:"created_at"`
	UpdatedAt      time.Time `json:"updated_at" db:"updated_at"`
}

// ProgressPct returns the percentage of target amount reached (0-100+).
// Returns 0 if there's no target set. Can exceed 100 if over-contributed.
//
// This is a VALUE RECEIVER method — it receives a copy of the VirtualAccount,
// not a pointer. Use value receivers for read-only methods that don't modify
// the struct. (See account.go IsCreditType for a longer explanation.)
//
// Note the nil check before dereferencing: *a.TargetAmount would PANIC if
// a.TargetAmount is nil. Always guard pointer dereferences with a nil check.
//
// Laravel analogy: Like an Eloquent accessor — getProgressPctAttribute().
// Django analogy: Like a @property on the Model class.
func (a VirtualAccount) ProgressPct() float64 {
	if a.TargetAmount == nil || *a.TargetAmount == 0 {
		return 0
	}
	return a.CurrentBalance / *a.TargetAmount * 100
}

// VirtualAccountAllocation links a transaction (or direct allocation) to a virtual account.
// This is a PIVOT TABLE model — it connects the many-to-many relationship
// between transactions and virtual accounts.
//
// Two types of allocations:
//   - Transaction-linked: TransactionID is set — created when a transaction is allocated to a VA.
//   - Direct: TransactionID is nil — created from the VA detail page to earmark existing funds.
//
// Positive amounts are contributions (income into the virtual account).
// Negative amounts are withdrawals (spending from the virtual account).
//
// Laravel analogy: This is the pivot table in a belongsToMany relationship,
// with an extra 'amount' column (withPivot('amount')).
//
// Django analogy: This is the "through" model in a ManyToManyField with
// through='VirtualAccountAllocation'.
type VirtualAccountAllocation struct {
	ID               string     `json:"id" db:"id"`
	TransactionID    *string    `json:"transaction_id" db:"transaction_id"`         // nullable — NULL for direct allocations
	VirtualAccountID string     `json:"virtual_account_id" db:"virtual_account_id"` // FK to virtual_accounts table
	Amount           float64    `json:"amount" db:"amount"`                         // positive = contribution, negative = withdrawal
	Note             *string    `json:"note" db:"note"`                             // optional note for direct allocations
	AllocatedAt      *time.Time `json:"allocated_at" db:"allocated_at"`             // date of direct allocation (NULL for tx-linked)
	CreatedAt        time.Time  `json:"created_at" db:"created_at"`
}
