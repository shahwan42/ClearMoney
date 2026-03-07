package models

import "time"

// InstallmentPlan tracks a purchase split into monthly payments (like TRU EPP or credit card installments).
// Similar to a Laravel model with computed accessors — IsComplete() and PaidInstallments() are
// value-receiver methods, meaning they don't modify the struct (like Django @property methods).
type InstallmentPlan struct {
	ID                     string    `json:"id" db:"id"`
	AccountID              string    `json:"account_id" db:"account_id"`              // FK to Account (typically a credit card)
	Description            string    `json:"description" db:"description"`            // what was purchased
	TotalAmount            float64   `json:"total_amount" db:"total_amount"`          // full purchase price
	NumInstallments        int       `json:"num_installments" db:"num_installments"`  // total months (e.g., 12)
	MonthlyAmount          float64   `json:"monthly_amount" db:"monthly_amount"`      // TotalAmount / NumInstallments
	StartDate              time.Time `json:"start_date" db:"start_date"`
	RemainingInstallments  int       `json:"remaining_installments" db:"remaining_installments"` // decremented each month
	CreatedAt              time.Time `json:"created_at" db:"created_at"`
	UpdatedAt              time.Time `json:"updated_at" db:"updated_at"`
}

// IsComplete returns true if all installments have been paid.
func (p InstallmentPlan) IsComplete() bool {
	return p.RemainingInstallments <= 0
}

// PaidInstallments returns how many installments have been paid.
func (p InstallmentPlan) PaidInstallments() int {
	return p.NumInstallments - p.RemainingInstallments
}
