package models

import (
	"encoding/json"
	"time"
)

// AccountType represents the kind of bank account.
type AccountType string

const (
	AccountTypeChecking    AccountType = "checking"     // standard debit account
	AccountTypeSavings     AccountType = "savings"      // savings account
	AccountTypeCurrent     AccountType = "current"      // current/business account
	AccountTypePrepaid     AccountType = "prepaid"      // prepaid card (e.g., Fawry)
	AccountTypeCreditCard  AccountType = "credit_card"  // credit card (balance goes negative)
	AccountTypeCreditLimit AccountType = "credit_limit" // credit line (e.g., TRU EPP)
)

// Currency represents the supported currencies.
type Currency string

const (
	CurrencyEGP Currency = "EGP"
	CurrencyUSD Currency = "USD"
)

// Account represents a single financial account within an institution.
// For example, "HSBC USD Checking" or "CIB Savings".
//
// Balance conventions:
//   - Debit accounts (checking, savings): positive balance = money you have
//   - Credit accounts (credit_card): negative balance = money you owe
//     e.g., -120,000 means you've used 120K of your credit limit
//
// json.RawMessage for Metadata lets us store arbitrary JSON (like billing
// cycle info) without defining a rigid struct — similar to a JSON column
// in Laravel or Django's JSONField.
type Account struct {
	ID             string          `json:"id" db:"id"`
	InstitutionID  string          `json:"institution_id" db:"institution_id"`
	Name           string          `json:"name" db:"name"`
	Type           AccountType     `json:"type" db:"type"`
	Currency       Currency        `json:"currency" db:"currency"`
	CurrentBalance float64         `json:"current_balance" db:"current_balance"` // cached, updated on every transaction
	InitialBalance float64         `json:"initial_balance" db:"initial_balance"` // set once at account creation
	CreditLimit    *float64        `json:"credit_limit,omitempty" db:"credit_limit"` // nil for debit accounts
	IsDormant      bool            `json:"is_dormant" db:"is_dormant"`
	RoleTags       []string        `json:"role_tags" db:"role_tags"` // e.g., ["primary-income", "building-fund"]
	DisplayOrder   int             `json:"display_order" db:"display_order"`
	Metadata       json.RawMessage `json:"metadata" db:"metadata"` // flexible JSONB for billing cycle info, etc.
	HealthConfig   json.RawMessage `json:"health_config" db:"health_config"` // TASK-068: JSONB for min_balance, min_monthly_deposit
	CreatedAt      time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt      time.Time       `json:"updated_at" db:"updated_at"`
}

// AccountHealthConfig holds account health constraints.
// Stored as JSONB in the health_config column.
type AccountHealthConfig struct {
	MinBalance        *float64 `json:"min_balance,omitempty"`         // alert if balance drops below
	MinMonthlyDeposit *float64 `json:"min_monthly_deposit,omitempty"` // alert if no deposit >= this amount
}

// GetHealthConfig parses the JSONB health_config into a typed struct.
// Returns nil if not configured.
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
// These accounts have special balance behavior (goes negative on spending).
func (a Account) IsCreditType() bool {
	return a.Type == AccountTypeCreditCard || a.Type == AccountTypeCreditLimit
}

// AvailableCredit returns how much credit is still available.
// For a card with 500K limit and -120K balance: available = 500K + (-120K) = 380K.
func (a Account) AvailableCredit() float64 {
	if a.CreditLimit == nil {
		return 0
	}
	// CurrentBalance is negative for credit accounts, so addition is correct:
	// limit(500000) + balance(-120000) = 380000 available
	return *a.CreditLimit + a.CurrentBalance
}
