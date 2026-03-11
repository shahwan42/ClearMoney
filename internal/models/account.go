// Package models — account.go defines the Account model and its methods.
//
// Account is one of the most important models — it represents a single financial
// account (bank account, credit card, prepaid card, etc.) within an institution.
//
// This file demonstrates several important Go patterns:
//   - Type aliases as enums (AccountType, Currency)
//   - json.RawMessage for flexible JSONB columns
//   - Value-receiver methods on structs (IsCreditType, AvailableCredit, etc.)
//   - Pointer types for nullable fields (*float64, *string)
package models

import (
	"encoding/json"
	"time"
)

// AccountType represents the kind of bank account.
//
// Same enum pattern as InstitutionType (see institution.go for the full explanation).
// Each constant maps to a value stored in the PostgreSQL "type" column.
type AccountType string

const (
	AccountTypeSavings     AccountType = "savings"      // savings account (typically higher interest, fewer transactions)
	AccountTypeCurrent     AccountType = "current"      // standard debit/current account (like a daily-use bank account)
	AccountTypePrepaid     AccountType = "prepaid"      // prepaid card (e.g., Fawry) — balance is loaded up front
	AccountTypeCreditCard  AccountType = "credit_card"  // credit card — balance goes NEGATIVE when you spend (owe money)
	AccountTypeCreditLimit AccountType = "credit_limit" // credit line (e.g., TRU EPP) — similar to credit card behavior
)

// Currency represents the supported currencies.
//
// Currently supports EGP (Egyptian Pound) and USD (US Dollar).
// Adding a new currency requires adding a constant here and updating
// the exchange rate and formatting logic throughout the app.
type Currency string

const (
	CurrencyEGP Currency = "EGP" // Egyptian Pound — the primary currency
	CurrencyUSD Currency = "USD" // US Dollar — for USD-denominated accounts
)

// Account represents a single financial account within an institution.
// For example, "HSBC USD Current" or "CIB Savings".
//
// Balance conventions:
//   - Debit accounts (current, savings): positive balance = money you have
//   - Credit accounts (credit_card): negative balance = money you owe
//     e.g., -120,000 means you've used 120K of your credit limit
//
// json.RawMessage explained:
//   json.RawMessage is Go's way of saying "store this as raw JSON bytes — don't
//   parse it into a typed struct yet." It maps to PostgreSQL's JSONB column type.
//
//   Laravel analogy: Like a JSON column with $casts = ['metadata' => 'array'].
//   But instead of auto-casting, you manually call json.Unmarshal() when you need
//   the typed data (see GetHealthConfig below).
//
//   Django analogy: Like models.JSONField() — stores arbitrary JSON without a
//   fixed schema. You access it as a dict in Python; here you access it as raw
//   bytes and unmarshal on demand.
//
//   See: https://pkg.go.dev/encoding/json#RawMessage
//
// RoleTags ([]string) maps to PostgreSQL's text[] (array) column type.
// In Go, slices ([]string) are dynamically-sized arrays — like PHP arrays or
// Python lists, but typed. They're used here instead of a separate tags table
// for simplicity.
type Account struct {
	ID             string          `json:"id" db:"id"`
	InstitutionID  string          `json:"institution_id" db:"institution_id"`     // FK to Institution — like $table->foreignId('institution_id') in Laravel
	Name           string          `json:"name" db:"name"`
	Type           AccountType     `json:"type" db:"type"`
	Currency       Currency        `json:"currency" db:"currency"`
	CurrentBalance float64         `json:"current_balance" db:"current_balance"`   // cached balance, updated atomically on every transaction (denormalized for perf)
	InitialBalance float64         `json:"initial_balance" db:"initial_balance"`   // set once at account creation — used for reconciliation
	CreditLimit    *float64        `json:"credit_limit,omitempty" db:"credit_limit"` // *float64 = nullable; nil for debit accounts, set for credit cards (e.g., 500000.0)
	IsDormant      bool            `json:"is_dormant" db:"is_dormant"`             // hidden from active lists but not deleted
	RoleTags       []string        `json:"role_tags" db:"role_tags"`               // e.g., ["primary-income", "virtual-fund"] — Go slice maps to PostgreSQL text[]
	DisplayOrder   int             `json:"display_order" db:"display_order"`       // UI ordering — lower numbers appear first
	Metadata       json.RawMessage `json:"metadata" db:"metadata"`                // flexible JSONB for billing cycle info, etc. (see json.RawMessage explanation above)
	HealthConfig   json.RawMessage `json:"health_config" db:"health_config"`      // JSONB for min_balance, min_monthly_deposit rules
	CreatedAt      time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt      time.Time       `json:"updated_at" db:"updated_at"`
}

// AccountHealthConfig holds account health constraint rules.
// Stored as JSONB in the health_config column and parsed on demand.
//
// This is a "typed view" of the raw JSON — you store json.RawMessage in the
// Account struct, then unmarshal it into this typed struct when you need it.
// Think of it like a DTO (Data Transfer Object) that gives structure to the
// otherwise-unstructured JSONB data.
//
// Laravel analogy: Like defining a $casts entry that maps a JSON column to a
// value object or a Spatie Data DTO.
type AccountHealthConfig struct {
	MinBalance        *float64 `json:"min_balance,omitempty"`         // alert if balance drops below this threshold
	MinMonthlyDeposit *float64 `json:"min_monthly_deposit,omitempty"` // alert if no deposit >= this amount arrives during the month
}

// GetHealthConfig parses the JSONB health_config into a typed struct.
// Returns nil if not configured (empty, null, or no meaningful values).
//
// This is a VALUE RECEIVER method — func (a Account) means it receives a COPY
// of the Account struct, not a pointer to it. This is fine because we're only
// reading data, not modifying the struct.
//
// Laravel analogy: Like an Eloquent accessor — getHealthConfigAttribute() — that
// transforms a raw JSON column into a typed object.
//
// Django analogy: Like a @property on a Model that deserializes a JSONField
// into a dataclass.
//
// See: https://pkg.go.dev/encoding/json#Unmarshal for how JSON parsing works in Go
func (a Account) GetHealthConfig() *AccountHealthConfig {
	if len(a.HealthConfig) == 0 || string(a.HealthConfig) == "null" {
		return nil
	}
	var cfg AccountHealthConfig
	if err := json.Unmarshal(a.HealthConfig, &cfg); err != nil {
		return nil
	}
	if cfg.MinBalance == nil && cfg.MinMonthlyDeposit == nil {
		return nil
	}
	return &cfg
}

// IsCreditType returns true for credit cards and credit limit accounts.
// These accounts have special balance behavior — the balance goes negative
// when you spend, and payments bring it back toward zero.
//
// This is a value-receiver method. In Go, methods are defined OUTSIDE the
// struct body (unlike PHP/Python where methods are inside the class).
// The receiver (a Account) is like PHP's $this or Python's self.
//
// Value receiver vs pointer receiver:
//   - func (a Account) — receives a COPY, can't modify the original (use for read-only)
//   - func (a *Account) — receives a POINTER, can modify the original (use for mutations)
//
// See: https://go.dev/tour/methods/4 for value vs pointer receivers
func (a Account) IsCreditType() bool {
	return a.Type == AccountTypeCreditCard || a.Type == AccountTypeCreditLimit
}

// AvailableCredit returns how much credit is still available on a credit account.
//
// Example calculation for a card with 500K limit and -120K balance:
//   available = limit + balance = 500,000 + (-120,000) = 380,000
//
// Note the pointer dereference: *a.CreditLimit uses the * operator to get the
// value that the pointer points to. Since CreditLimit is *float64 (a pointer),
// you can't use it directly in arithmetic — you must dereference it first.
// If the pointer is nil (no credit limit), we return 0.
//
// See: https://go.dev/tour/moretypes/1 for pointer basics
func (a Account) AvailableCredit() float64 {
	if a.CreditLimit == nil {
		return 0
	}
	// CurrentBalance is negative for credit accounts, so addition is correct:
	// limit(500000) + balance(-120000) = 380000 available
	return *a.CreditLimit + a.CurrentBalance
}
