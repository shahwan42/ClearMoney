package models

import (
	"encoding/json"
	"time"
)

type AccountType string

const (
	AccountTypeChecking    AccountType = "checking"
	AccountTypeSavings     AccountType = "savings"
	AccountTypeCurrent     AccountType = "current"
	AccountTypePrepaid     AccountType = "prepaid"
	AccountTypeCreditCard  AccountType = "credit_card"
	AccountTypeCreditLimit AccountType = "credit_limit"
)

type Currency string

const (
	CurrencyEGP Currency = "EGP"
	CurrencyUSD Currency = "USD"
)

type Account struct {
	ID             string          `json:"id" db:"id"`
	InstitutionID  string          `json:"institution_id" db:"institution_id"`
	Name           string          `json:"name" db:"name"`
	Type           AccountType     `json:"type" db:"type"`
	Currency       Currency        `json:"currency" db:"currency"`
	CurrentBalance float64         `json:"current_balance" db:"current_balance"`
	InitialBalance float64         `json:"initial_balance" db:"initial_balance"`
	CreditLimit    *float64        `json:"credit_limit,omitempty" db:"credit_limit"`
	IsDormant      bool            `json:"is_dormant" db:"is_dormant"`
	RoleTags       []string        `json:"role_tags" db:"role_tags"`
	DisplayOrder   int             `json:"display_order" db:"display_order"`
	Metadata       json.RawMessage `json:"metadata" db:"metadata"`
	CreatedAt      time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt      time.Time       `json:"updated_at" db:"updated_at"`
}

func (a Account) IsCreditType() bool {
	return a.Type == AccountTypeCreditCard || a.Type == AccountTypeCreditLimit
}

func (a Account) AvailableCredit() float64 {
	if a.CreditLimit == nil {
		return 0
	}
	return *a.CreditLimit + a.CurrentBalance
}
