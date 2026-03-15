// Package models — transaction.go defines the Transaction model.
//
// Transaction is the most important model in the system — every money movement
// (expense, income, transfer, exchange, loan) creates one or two Transaction records.
//
// This model has the most nullable pointer fields because many columns only apply
// to specific transaction types. For example, ExchangeRate is only relevant for
// exchange transactions, and PersonID is only set for loan transactions.
//
// Laravel analogy: This is the central Eloquent model that most other models
// relate to. It would have multiple belongsTo relationships (account, category,
// person, recurringRule) and a hasOne for the linked transaction.
//
// Django analogy: The primary Model class with multiple ForeignKey fields, some
// with null=True, blank=True for optional relationships.
package models

import "time"

// TransactionType defines what kind of money movement this is.
//
// These types determine business logic throughout the app:
//   - How the account balance is affected (BalanceDelta calculation)
//   - Which fields are required vs optional
//   - Whether linked transactions are created
//   - Whether a Person record is updated
type TransactionType string

const (
	TransactionTypeExpense       TransactionType = "expense"        // money going out (decreases account balance)
	TransactionTypeIncome        TransactionType = "income"         // money coming in (increases account balance)
	TransactionTypeTransfer      TransactionType = "transfer"       // between own accounts (same currency) — creates TWO linked records
	TransactionTypeExchange      TransactionType = "exchange"       // USD to EGP conversion (or vice versa) — creates TWO linked records
	TransactionTypeLoanOut       TransactionType = "loan_out"       // I lent money to someone — decreases my balance, increases Person.NetBalance
	TransactionTypeLoanIn        TransactionType = "loan_in"        // I borrowed money from someone — increases my balance, decreases Person.NetBalance
	TransactionTypeLoanRepayment TransactionType = "loan_repayment" // partial or full loan repayment — adjusts both account and Person.NetBalance
)

// Transaction is the core record — every money movement creates one (or two, for transfers).
//
// Key design patterns:
//
//   1. AMOUNT IS ALWAYS POSITIVE. The Type field determines if it's a debit or credit.
//      The actual signed impact is stored in BalanceDelta (e.g., -500 for a 500 expense).
//      This makes queries and display logic simpler — you never wonder if Amount is
//      negative or positive.
//
//   2. DOUBLE-ENTRY FOR TRANSFERS. Transfers and exchanges create TWO Transaction
//      records — one per account — connected via LinkedTransactionID. This is a
//      simplified form of double-entry bookkeeping. For example, transferring 1000 EGP
//      from Account A to Account B creates:
//        - Record 1: AccountID=A, BalanceDelta=-1000, LinkedTransactionID=Record2.ID
//        - Record 2: AccountID=B, BalanceDelta=+1000, LinkedTransactionID=Record1.ID
//
//   3. NULLABLE POINTER FIELDS. Many columns only apply to specific types:
//        - *string and *float64 are Go's way of representing nullable values
//        - nil = "not applicable" or SQL NULL
//        - You MUST check for nil before dereferencing: if tx.ExchangeRate != nil { rate := *tx.ExchangeRate }
//        - Dereferencing a nil pointer causes a runtime panic (like PHP's
//          "attempt to read property on null" or Python's AttributeError on None)
//
//   4. BALANCE_DELTA for reconciliation. This is the actual signed impact on the
//      account's balance. The reconciliation job (internal/jobs/reconcile.go) uses
//      this field to verify that InitialBalance + SUM(balance_delta) == CurrentBalance.
type Transaction struct {
	ID                  string          `json:"id" db:"id"`
	Type                TransactionType `json:"type" db:"type"`
	Amount              float64         `json:"amount" db:"amount"`                                        // always positive — Type + BalanceDelta determine direction
	Currency            Currency        `json:"currency" db:"currency"`
	AccountID           string          `json:"account_id" db:"account_id"`                                // the primary account affected (FK to accounts table)
	CounterAccountID    *string         `json:"counter_account_id,omitempty" db:"counter_account_id"`      // *string = nullable; set only for transfers/exchanges (the "other" account)
	CategoryID          *string         `json:"category_id,omitempty" db:"category_id"`                    // nil for transfers (no category needed); FK to categories
	Date                time.Time       `json:"date" db:"date"`                                            // date of the transaction (DATE in PostgreSQL)
	Time                *string         `json:"time,omitempty" db:"time"`                                  // optional time-of-day as string (e.g., "14:30") — stored as text, not timestamp
	Note                *string         `json:"note,omitempty" db:"note"`                                  // optional user note/description
	Tags                []string        `json:"tags" db:"tags"`                                            // Go slices map to PostgreSQL text[] arrays — used for filtering/search
	ExchangeRate        *float64        `json:"exchange_rate,omitempty" db:"exchange_rate"`                 // only for "exchange" type (e.g., 50.5 = 1 USD = 50.5 EGP)
	CounterAmount       *float64        `json:"counter_amount,omitempty" db:"counter_amount"`              // amount in the other currency for exchanges (e.g., if Amount=100 USD, CounterAmount=5050 EGP)
	FeeAmount           *float64        `json:"fee_amount,omitempty" db:"fee_amount"`                      // bank fee deducted (if any) — recorded separately from the main amount
	FeeAccountID        *string         `json:"fee_account_id,omitempty" db:"fee_account_id"`              // which account the fee was charged to (may differ from AccountID)
	PersonID            *string         `json:"person_id,omitempty" db:"person_id"`                        // FK to Person — set for loan_out, loan_in, loan_repayment transactions
	LinkedTransactionID *string         `json:"linked_transaction_id,omitempty" db:"linked_transaction_id"` // the other half of a transfer/exchange pair (self-referencing FK)
	RecurringRuleID     *string         `json:"recurring_rule_id,omitempty" db:"recurring_rule_id"`         // FK to RecurringRule that auto-generated this transaction
	BalanceDelta        float64         `json:"balance_delta" db:"balance_delta"`                           // actual signed impact on AccountID's balance (e.g., -500 for an expense, +1000 for income)
	CreatedAt           time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt           time.Time       `json:"updated_at" db:"updated_at"`
}
