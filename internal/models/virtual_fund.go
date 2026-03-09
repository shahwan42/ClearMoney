// Package models — virtual_fund.go defines the VirtualFund and FundAllocation models.
//
// Virtual funds are like "buckets" or "envelopes" in envelope budgeting.
// They replace the hardcoded is_building_fund flag with a flexible system
// where users can create any number of savings goals.
//
// In Laravel terms, these are Eloquent models. In Django, these are Model classes.
package models

import "time"

// VirtualFund represents a user-defined savings bucket (e.g., "Building Fund",
// "Emergency Fund", "Vacation"). Each fund tracks a balance computed from
// transaction allocations.
type VirtualFund struct {
	ID             string    `json:"id" db:"id"`
	Name           string    `json:"name" db:"name"`
	TargetAmount   *float64  `json:"target_amount" db:"target_amount"` // nil = no target
	CurrentBalance float64   `json:"current_balance" db:"current_balance"`
	Icon           string    `json:"icon" db:"icon"`
	Color          string    `json:"color" db:"color"`
	IsArchived     bool      `json:"is_archived" db:"is_archived"`
	DisplayOrder   int       `json:"display_order" db:"display_order"`
	CreatedAt      time.Time `json:"created_at" db:"created_at"`
	UpdatedAt      time.Time `json:"updated_at" db:"updated_at"`
}

// ProgressPct returns the percentage of target amount reached (0-100+).
// Returns 0 if there's no target set.
func (f VirtualFund) ProgressPct() float64 {
	if f.TargetAmount == nil || *f.TargetAmount == 0 {
		return 0
	}
	return f.CurrentBalance / *f.TargetAmount * 100
}

// FundAllocation links a transaction to a virtual fund with a specific amount.
// Positive amounts are contributions (income), negative are withdrawals (expense).
type FundAllocation struct {
	ID            string    `json:"id" db:"id"`
	TransactionID string    `json:"transaction_id" db:"transaction_id"`
	VirtualFundID string    `json:"virtual_fund_id" db:"virtual_fund_id"`
	Amount        float64   `json:"amount" db:"amount"`
	CreatedAt     time.Time `json:"created_at" db:"created_at"`
}
