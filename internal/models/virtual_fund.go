// Package models — virtual_fund.go defines the VirtualFund and FundAllocation models.
//
// Virtual funds implement "envelope budgeting" — a method where you mentally allocate
// money into different buckets (envelopes) for different purposes. The actual money
// stays in your bank accounts, but the virtual funds track how much is earmarked
// for each goal.
//
// This replaces the hardcoded is_building_fund boolean flag on transactions with
// a flexible system where users can create any number of savings goals. The old flag
// is kept for backward compatibility but new allocations use this system.
//
// Laravel analogy: VirtualFund is an Eloquent model with a many-to-many relationship
// to Transaction via the FundAllocation pivot table. In Laravel, you'd define this
// with belongsToMany('Transaction')->withPivot('amount')->withTimestamps().
//
// Django analogy: VirtualFund and FundAllocation are like a Model with a ManyToManyField
// using a custom through table. The FundAllocation model is the "through" model that
// stores the amount allocated per transaction.
package models

import "time"

// VirtualFund represents a user-defined savings bucket (e.g., "Building Fund",
// "Emergency Fund", "Vacation"). Each fund tracks a balance computed from
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
type VirtualFund struct {
	ID             string    `json:"id" db:"id"`
	Name           string    `json:"name" db:"name"`
	TargetAmount   *float64  `json:"target_amount" db:"target_amount"`     // *float64 = nullable; nil means "open-ended fund with no target"
	CurrentBalance float64   `json:"current_balance" db:"current_balance"` // cached sum of all allocations (denormalized for performance)
	Icon           string    `json:"icon" db:"icon"`                       // emoji or icon identifier for UI display
	Color          string    `json:"color" db:"color"`                     // hex color for progress bar and card styling
	IsArchived     bool      `json:"is_archived" db:"is_archived"`         // soft-archive: hidden from active list but kept for history
	DisplayOrder   int       `json:"display_order" db:"display_order"`     // UI ordering — lower numbers appear first
	CreatedAt      time.Time `json:"created_at" db:"created_at"`
	UpdatedAt      time.Time `json:"updated_at" db:"updated_at"`
}

// ProgressPct returns the percentage of target amount reached (0-100+).
// Returns 0 if there's no target set. Can exceed 100 if over-contributed.
//
// This is a VALUE RECEIVER method — it receives a copy of the VirtualFund,
// not a pointer. Use value receivers for read-only methods that don't modify
// the struct. (See account.go IsCreditType for a longer explanation.)
//
// Note the nil check before dereferencing: *f.TargetAmount would PANIC if
// f.TargetAmount is nil. Always guard pointer dereferences with a nil check.
//
// Laravel analogy: Like an Eloquent accessor — getProgressPctAttribute().
// Django analogy: Like a @property on the Model class.
func (f VirtualFund) ProgressPct() float64 {
	if f.TargetAmount == nil || *f.TargetAmount == 0 {
		return 0
	}
	return f.CurrentBalance / *f.TargetAmount * 100
}

// FundAllocation links a transaction to a virtual fund with a specific amount.
// This is a PIVOT TABLE model — it connects the many-to-many relationship
// between transactions and virtual funds.
//
// Positive amounts are contributions (income into the fund).
// Negative amounts are withdrawals (spending from the fund).
//
// A single transaction can be split across multiple funds (e.g., a salary
// deposit might allocate E£2,000 to "Building Fund" and E£500 to "Emergency Fund").
//
// Laravel analogy: This is the pivot table in a belongsToMany relationship,
// with an extra 'amount' column (withPivot('amount')).
//
// Django analogy: This is the "through" model in a ManyToManyField with
// through='FundAllocation'.
type FundAllocation struct {
	ID            string    `json:"id" db:"id"`
	TransactionID string    `json:"transaction_id" db:"transaction_id"` // FK to transactions table
	VirtualFundID string    `json:"virtual_fund_id" db:"virtual_fund_id"` // FK to virtual_funds table
	Amount        float64   `json:"amount" db:"amount"`                 // positive = contribution, negative = withdrawal
	CreatedAt     time.Time `json:"created_at" db:"created_at"`         // no UpdatedAt — allocations are immutable once created
}
