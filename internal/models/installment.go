package models

import "time"

// InstallmentPlan tracks a purchase split into monthly payments (like TRU EPP).
type InstallmentPlan struct {
	ID                     string    `json:"id" db:"id"`
	AccountID              string    `json:"account_id" db:"account_id"`
	Description            string    `json:"description" db:"description"`
	TotalAmount            float64   `json:"total_amount" db:"total_amount"`
	NumInstallments        int       `json:"num_installments" db:"num_installments"`
	MonthlyAmount          float64   `json:"monthly_amount" db:"monthly_amount"`
	StartDate              time.Time `json:"start_date" db:"start_date"`
	RemainingInstallments  int       `json:"remaining_installments" db:"remaining_installments"`
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
