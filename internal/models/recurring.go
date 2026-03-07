package models

import (
	"encoding/json"
	"time"
)

// RecurringFrequency defines how often a rule fires.
type RecurringFrequency string

const (
	RecurringFrequencyMonthly RecurringFrequency = "monthly"
	RecurringFrequencyWeekly  RecurringFrequency = "weekly"
)

// RecurringRule defines a template for transactions that repeat on a schedule.
// The template_transaction JSONB stores all fields of a transaction except the date.
type RecurringRule struct {
	ID                  string             `json:"id" db:"id"`
	TemplateTransaction json.RawMessage    `json:"template_transaction" db:"template_transaction"`
	Frequency           RecurringFrequency `json:"frequency" db:"frequency"`
	DayOfMonth          *int               `json:"day_of_month,omitempty" db:"day_of_month"`
	NextDueDate         time.Time          `json:"next_due_date" db:"next_due_date"`
	IsActive            bool               `json:"is_active" db:"is_active"`
	AutoConfirm         bool               `json:"auto_confirm" db:"auto_confirm"`
	CreatedAt           time.Time          `json:"created_at" db:"created_at"`
	UpdatedAt           time.Time          `json:"updated_at" db:"updated_at"`
}

// TransactionTemplate is the deserialized form of template_transaction.
type TransactionTemplate struct {
	Type       TransactionType `json:"type"`
	Amount     float64         `json:"amount"`
	Currency   Currency        `json:"currency"`
	AccountID  string          `json:"account_id"`
	CategoryID *string         `json:"category_id,omitempty"`
	Note       *string         `json:"note,omitempty"`
}
