package models

import "time"

// TransactionType defines what kind of money movement this is.
type TransactionType string

const (
	TransactionTypeExpense       TransactionType = "expense"        // money going out
	TransactionTypeIncome        TransactionType = "income"         // money coming in
	TransactionTypeTransfer      TransactionType = "transfer"       // between own accounts (same currency)
	TransactionTypeExchange      TransactionType = "exchange"       // USD ↔ EGP conversion
	TransactionTypeLoanOut       TransactionType = "loan_out"       // I lent money to someone
	TransactionTypeLoanIn        TransactionType = "loan_in"        // I borrowed money from someone
	TransactionTypeLoanRepayment TransactionType = "loan_repayment" // partial or full loan repayment
)

// Transaction is the core record — every money movement creates one (or two, for transfers).
//
// Key design patterns:
//   - Amount is always positive. The Type determines if it's a debit or credit.
//   - Transfers and exchanges create TWO linked transactions (one per account),
//     connected via LinkedTransactionID — like double-entry bookkeeping.
//   - Pointer fields (*string, *float64) are nullable — nil means "not applicable".
//     e.g., ExchangeRate is only set for exchange transactions.
type Transaction struct {
	ID                  string          `json:"id" db:"id"`
	Type                TransactionType `json:"type" db:"type"`
	Amount              float64         `json:"amount" db:"amount"`   // always positive — Type determines direction
	Currency            Currency        `json:"currency" db:"currency"`
	AccountID           string          `json:"account_id" db:"account_id"`             // the primary account affected
	CounterAccountID    *string         `json:"counter_account_id,omitempty" db:"counter_account_id"` // *string = nullable; set only for transfers/exchanges (the "other" account)
	CategoryID          *string         `json:"category_id,omitempty" db:"category_id"` // nil for transfers (no category needed)
	Date                time.Time       `json:"date" db:"date"`
	Time                *string         `json:"time,omitempty" db:"time"` // optional time-of-day as string (e.g., "14:30")
	Note                *string         `json:"note,omitempty" db:"note"`
	Tags                []string        `json:"tags" db:"tags"`           // Go slices map to PostgreSQL text[] arrays
	ExchangeRate        *float64        `json:"exchange_rate,omitempty" db:"exchange_rate"`   // only for "exchange" type (e.g., 50.5 EGP per USD)
	CounterAmount       *float64        `json:"counter_amount,omitempty" db:"counter_amount"` // amount in the other currency for exchanges
	FeeAmount           *float64        `json:"fee_amount,omitempty" db:"fee_amount"`         // bank fee deducted (if any)
	FeeAccountID        *string         `json:"fee_account_id,omitempty" db:"fee_account_id"` // which account the fee was charged to
	PersonID            *string         `json:"person_id,omitempty" db:"person_id"`           // FK to Person — set for loan transactions
	LinkedTransactionID *string         `json:"linked_transaction_id,omitempty" db:"linked_transaction_id"` // the other half of a transfer/exchange pair
	IsBuildingFund      bool            `json:"is_building_fund" db:"is_building_fund"` // flags contributions to a building savings goal
	RecurringRuleID     *string         `json:"recurring_rule_id,omitempty" db:"recurring_rule_id"` // FK to RecurringRule that generated this
	BalanceDelta        float64         `json:"balance_delta" db:"balance_delta"` // actual signed impact on AccountID's balance (e.g., -500 for an expense)
	CreatedAt           time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt           time.Time       `json:"updated_at" db:"updated_at"`
}
