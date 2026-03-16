// Package models — recurring.go defines the RecurringRule and TransactionTemplate models.
//
// Recurring rules are templates for transactions that repeat on a schedule (e.g.,
// monthly salary, weekly groceries, monthly Netflix subscription). When a rule's
// NextDueDate arrives, the system either auto-creates the transaction or prompts
// the user for confirmation.
//
// This file demonstrates two important Go/JSON patterns:
//   1. json.RawMessage for storing a JSONB "template" that's parsed on demand
//   2. A typed struct (TransactionTemplate) that gives shape to the raw JSON
//
// Laravel analogy: Like a scheduled task registered in Kernel.php, but instead
// of running a command, it creates a Transaction record. The rule stores a
// "template" of the transaction in a JSON column, similar to how you might
// store event payloads in a jobs table.
//
// Django analogy: Like a django-celery-beat PeriodicTask, but for financial
// transactions. The TemplateTransaction JSONB is like a JSONField that stores
// the transaction prototype to be cloned on each occurrence.
package models

import (
	"encoding/json"
	"time"
)

// RecurringFrequency defines how often a rule fires.
// Monthly rules need a DayOfMonth; weekly rules fire on the same weekday.
type RecurringFrequency string

const (
	RecurringFrequencyMonthly RecurringFrequency = "monthly" // fires once per month on DayOfMonth (e.g., salary on the 25th)
	RecurringFrequencyWeekly  RecurringFrequency = "weekly"  // fires once per week on the same weekday
)

// RecurringRule defines a template for transactions that repeat on a schedule.
//
// How it works:
//   1. User creates a rule with a template transaction (amount, account, category, etc.)
//   2. On app startup, the system checks all active rules where NextDueDate <= today
//   3. If AutoConfirm is true: a real Transaction is created automatically
//   4. If AutoConfirm is false: the user is prompted to confirm/skip
//   5. After processing, NextDueDate advances to the next occurrence
//
// The TemplateTransaction field is json.RawMessage (raw JSON bytes). This means:
//   - It's stored as-is in the PostgreSQL JSONB column
//   - It's NOT automatically parsed into a Go struct
//   - When you need the typed data, call json.Unmarshal into a TransactionTemplate
//   - This is a deliberate design choice: the raw bytes are efficient for storage
//     and only parsed when actually needed
//
// See: https://pkg.go.dev/encoding/json#RawMessage
type RecurringRule struct {
	ID                  string             `json:"id" db:"id"`
	UserID              string             `json:"user_id" db:"user_id"`
	TemplateTransaction json.RawMessage    `json:"template_transaction" db:"template_transaction"` // raw JSON blob — decode with json.Unmarshal(&template) when needed
	Frequency           RecurringFrequency `json:"frequency" db:"frequency"`
	DayOfMonth          *int               `json:"day_of_month,omitempty" db:"day_of_month"` // *int = nullable; set for monthly rules (which day to fire), nil for weekly rules
	NextDueDate         time.Time          `json:"next_due_date" db:"next_due_date"`         // when this rule should fire next — advanced after each execution
	IsActive            bool               `json:"is_active" db:"is_active"`                 // toggle to pause without deleting
	AutoConfirm         bool               `json:"auto_confirm" db:"auto_confirm"`           // if true, auto-create the transaction; if false, show in "pending" list for manual confirmation
	CreatedAt           time.Time          `json:"created_at" db:"created_at"`
	UpdatedAt           time.Time          `json:"updated_at" db:"updated_at"`
}

// TransactionTemplate is the deserialized form of the TemplateTransaction JSONB column.
//
// This demonstrates the json.RawMessage -> typed struct pattern:
//   1. Store as json.RawMessage in the parent struct (flexible, no parsing cost)
//   2. Define a typed struct for when you need structured access
//   3. Use json.Unmarshal to convert: json.Unmarshal(rule.TemplateTransaction, &template)
//
// Laravel analogy: Like using $casts = ['template_transaction' => TransactionTemplateDTO::class]
// where TransactionTemplateDTO is a Spatie Data object or a custom cast class.
//
// Django analogy: Like a serializer class that deserializes a JSONField into a
// typed Python dataclass or Pydantic model.
//
// This struct intentionally has fewer fields than Transaction — it only stores the
// fields that stay the same across occurrences. The Date is computed at execution time,
// and fields like ID, BalanceDelta, CreatedAt are generated when the real Transaction
// is created.
type TransactionTemplate struct {
	Type       TransactionType `json:"type"`                    // expense, income, etc.
	Amount     float64         `json:"amount"`                  // the recurring amount
	Currency   Currency        `json:"currency"`                // EGP or USD
	AccountID  string          `json:"account_id"`              // which account to debit/credit
	CategoryID *string         `json:"category_id,omitempty"`   // optional category (nil for transfers)
	Note       *string         `json:"note,omitempty"`          // optional description (e.g., "Monthly Netflix")
}
