// Package models — installment.go defines the InstallmentPlan model for payment plans.
//
// Installment plans track purchases split into monthly payments — common with
// credit cards and services like TRU EPP (Easy Payment Plan). For example,
// buying a laptop for E£24,000 split into 12 monthly payments of E£2,000 each.
//
// Laravel analogy: An Eloquent model with computed accessor methods. IsComplete()
// and PaidInstallments() are like getIsCompleteAttribute() and
// getPaidInstallmentsAttribute() — but in Go they're explicit method calls,
// not magic properties.
//
// Django analogy: A Model with @property decorators for computed fields. The
// RemainingInstallments field is decremented externally (by the service layer),
// not auto-computed from dates.
package models

import "time"

// InstallmentPlan tracks a purchase split into monthly payments.
//
// Lifecycle:
//   1. User creates a plan: TotalAmount=24000, NumInstallments=12, RemainingInstallments=12
//   2. Each month, a recurring rule creates a transaction and decrements RemainingInstallments
//   3. When RemainingInstallments reaches 0, IsComplete() returns true
//
// MonthlyAmount is stored (not computed) because in practice, TotalAmount / NumInstallments
// might not divide evenly, and the user may want to set a rounded monthly amount.
//
// Two computed methods are provided:
//   - IsComplete(): checks if the plan is fully paid
//   - PaidInstallments(): returns how many payments have been made
//
// VALUE RECEIVER METHODS recap:
// Both methods use func (p InstallmentPlan) — note there's no * (pointer).
// This means they receive a COPY of the struct and cannot modify it.
// Use value receivers for read-only computations, pointer receivers for mutations.
// See: https://go.dev/tour/methods/4
type InstallmentPlan struct {
	ID                    string    `json:"id" db:"id"`
	UserID                string    `json:"user_id" db:"user_id"`
	AccountID             string    `json:"account_id" db:"account_id"`                         // FK to Account — typically a credit card or credit limit account
	Description           string    `json:"description" db:"description"`                       // what was purchased (e.g., "MacBook Pro 16-inch")
	TotalAmount           float64   `json:"total_amount" db:"total_amount"`                     // full purchase price before splitting (e.g., 24000.0)
	NumInstallments       int       `json:"num_installments" db:"num_installments"`             // total months in the plan (e.g., 12)
	MonthlyAmount         float64   `json:"monthly_amount" db:"monthly_amount"`                 // amount per installment (e.g., 2000.0)
	StartDate             time.Time `json:"start_date" db:"start_date"`                         // when the first installment is due
	RemainingInstallments int       `json:"remaining_installments" db:"remaining_installments"` // decremented each month when a payment is recorded
	CreatedAt             time.Time `json:"created_at" db:"created_at"`
	UpdatedAt             time.Time `json:"updated_at" db:"updated_at"`
}

// IsComplete returns true if all installments have been paid.
// This uses <= 0 (not == 0) as a safety guard — if RemainingInstallments
// somehow goes negative (bug), the plan is still considered complete.
func (p InstallmentPlan) IsComplete() bool {
	return p.RemainingInstallments <= 0
}

// PaidInstallments returns how many installments have been paid.
// Simple arithmetic: total - remaining = paid.
//
// Used in the UI to show progress like "8 of 12 paid" or render a progress bar.
func (p InstallmentPlan) PaidInstallments() int {
	return p.NumInstallments - p.RemainingInstallments
}
