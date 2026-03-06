package models

import "time"

type TransactionType string

const (
	TransactionTypeExpense       TransactionType = "expense"
	TransactionTypeIncome        TransactionType = "income"
	TransactionTypeTransfer      TransactionType = "transfer"
	TransactionTypeExchange      TransactionType = "exchange"
	TransactionTypeLoanOut       TransactionType = "loan_out"
	TransactionTypeLoanIn        TransactionType = "loan_in"
	TransactionTypeLoanRepayment TransactionType = "loan_repayment"
)

type Transaction struct {
	ID                  string          `json:"id" db:"id"`
	Type                TransactionType `json:"type" db:"type"`
	Amount              float64         `json:"amount" db:"amount"`
	Currency            Currency        `json:"currency" db:"currency"`
	AccountID           string          `json:"account_id" db:"account_id"`
	CounterAccountID    *string         `json:"counter_account_id,omitempty" db:"counter_account_id"`
	CategoryID          *string         `json:"category_id,omitempty" db:"category_id"`
	Date                time.Time       `json:"date" db:"date"`
	Time                *string         `json:"time,omitempty" db:"time"`
	Note                *string         `json:"note,omitempty" db:"note"`
	Tags                []string        `json:"tags" db:"tags"`
	ExchangeRate        *float64        `json:"exchange_rate,omitempty" db:"exchange_rate"`
	CounterAmount       *float64        `json:"counter_amount,omitempty" db:"counter_amount"`
	FeeAmount           *float64        `json:"fee_amount,omitempty" db:"fee_amount"`
	FeeAccountID        *string         `json:"fee_account_id,omitempty" db:"fee_account_id"`
	PersonID            *string         `json:"person_id,omitempty" db:"person_id"`
	LinkedTransactionID *string         `json:"linked_transaction_id,omitempty" db:"linked_transaction_id"`
	IsBuildingFund      bool            `json:"is_building_fund" db:"is_building_fund"`
	RecurringRuleID     *string         `json:"recurring_rule_id,omitempty" db:"recurring_rule_id"`
	CreatedAt           time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt           time.Time       `json:"updated_at" db:"updated_at"`
}
