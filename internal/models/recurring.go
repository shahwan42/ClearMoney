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
// Like Laravel's scheduled tasks or Django-celery periodic tasks, but for financial transactions.
// The template_transaction JSONB stores all fields of a transaction except the date.
type RecurringRule struct {
	ID                  string             `json:"id" db:"id"`
	TemplateTransaction json.RawMessage    `json:"template_transaction" db:"template_transaction"` // raw JSON blob — decoded into TransactionTemplate when needed
	Frequency           RecurringFrequency `json:"frequency" db:"frequency"`
	DayOfMonth          *int               `json:"day_of_month,omitempty" db:"day_of_month"` // *int = nullable; nil for weekly rules (only monthly needs a day)
	NextDueDate         time.Time          `json:"next_due_date" db:"next_due_date"`         // when this rule should fire next
	IsActive            bool               `json:"is_active" db:"is_active"`
	AutoConfirm         bool               `json:"auto_confirm" db:"auto_confirm"` // if true, auto-create the transaction; if false, prompt user
	CreatedAt           time.Time          `json:"created_at" db:"created_at"`
	UpdatedAt           time.Time          `json:"updated_at" db:"updated_at"`
}

// TransactionTemplate is the deserialized form of template_transaction.
// json.RawMessage stores raw bytes; this struct is what you get after json.Unmarshal.
// Similar to casting a JSON column to a DTO in Laravel ($casts) or using a serializer in Django.
type TransactionTemplate struct {
	Type       TransactionType `json:"type"`
	Amount     float64         `json:"amount"`
	Currency   Currency        `json:"currency"`
	AccountID  string          `json:"account_id"`
	CategoryID *string         `json:"category_id,omitempty"`
	Note       *string         `json:"note,omitempty"`
}
