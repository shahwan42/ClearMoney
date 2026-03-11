// transaction.go — TransactionService is the most critical service in ClearMoney.
//
// Every financial transaction (expense, income, transfer, exchange) MUST atomically
// update the associated account balance. If any step fails, everything rolls back.
//
// Laravel analogy: This is like wrapping operations in DB::transaction(function() { ... }).
// If the closure throws, Laravel auto-rolls back. In Go, we use sql.Tx (database transaction)
// with explicit Commit/Rollback calls — same concept, no magic.
//
// Django analogy: Like using transaction.atomic() as a context manager. If an exception
// occurs inside the block, the transaction is rolled back.
//
// Key Go patterns in this file:
//
//   - sql.Tx (database transactions): BeginTx() starts a transaction, Commit() finalizes,
//     Rollback() undoes. `defer dbTx.Rollback()` is safe — it's a no-op after Commit().
//     See: https://pkg.go.dev/database/sql#Tx
//
//   - Error wrapping with %w: fmt.Errorf("debiting source: %w", err) wraps the original
//     error. Callers can unwrap with errors.Is() or errors.As().
//     See: https://pkg.go.dev/errors
//
//   - Multiple return values: Create returns (Transaction, float64, error) — the created
//     record, the new balance, and any error. Go doesn't have exceptions; errors are values.
//
//   - Pointer fields (*string, *float64): represent nullable/optional values.
//     A nil pointer means "not set" — like NULL in SQL, null in PHP, None in Python.
//
//   - Setter injection: SetExchangeRateRepo() adds an optional dependency after construction.
//     Used when a dependency is optional or creates a circular reference if passed to constructor.
package service

import (
	"context"
	"fmt"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// TransactionService handles the business logic for creating, modifying,
// and deleting transactions — including atomic balance updates.
//
// This struct holds three repository dependencies. Note that rateRepo is
// set via a setter (optional), not the constructor (required). This is the
// "setter injection" pattern — used when a dependency is optional.
//
// In Laravel, you'd use the IoC container's $this->app->when(...)->needs(...)
// or make it nullable in the constructor. In Go, we use a setter method.
type TransactionService struct {
	txRepo   *repository.TransactionRepo
	accRepo  *repository.AccountRepo
	rateRepo *repository.ExchangeRateRepo // optional — set via SetExchangeRateRepo()
}

func NewTransactionService(txRepo *repository.TransactionRepo, accRepo *repository.AccountRepo) *TransactionService {
	return &TransactionService{txRepo: txRepo, accRepo: accRepo}
}

// SetExchangeRateRepo sets the exchange rate repository (optional dependency).
func (s *TransactionService) SetExchangeRateRepo(repo *repository.ExchangeRateRepo) {
	s.rateRepo = repo
}

// TxRepo returns the underlying transaction repository.
// Used by the credit card statement handler that needs direct repo access (TASK-071).
func (s *TransactionService) TxRepo() *repository.TransactionRepo {
	return s.txRepo
}

// Create validates and creates a transaction, atomically updating the account balance.
//
// Balance impact by transaction type:
//   - expense:  balance -= amount (money goes out)
//   - income:   balance += amount (money comes in)
//
// Returns the created transaction and the new account balance.
func (s *TransactionService) Create(ctx context.Context, tx models.Transaction) (models.Transaction, float64, error) {
	if err := s.validateBasic(tx); err != nil {
		return models.Transaction{}, 0, err
	}

	// Calculate balance delta based on transaction type
	delta := s.balanceDelta(tx)

	// Credit card validation: check if expense would exceed credit limit
	if delta < 0 {
		acc, err := s.accRepo.GetByID(ctx, tx.AccountID)
		if err == nil && acc.IsCreditType() && acc.CreditLimit != nil {
			newBalance := acc.CurrentBalance + delta
			if newBalance < -*acc.CreditLimit {
				return models.Transaction{}, 0, fmt.Errorf(
					"would exceed credit limit (available: %.2f)", acc.AvailableCredit())
			}
		}
	}

	// Begin a database transaction (the SQL kind, not the financial kind!)
	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, 0, fmt.Errorf("beginning transaction: %w", err)
	}
	// defer Rollback is safe — it's a no-op if Commit was already called.
	defer dbTx.Rollback()

	// 1. Insert the transaction record with its balance impact
	tx.BalanceDelta = delta
	created, err := s.txRepo.CreateTx(ctx, dbTx, tx)
	if err != nil {
		return models.Transaction{}, 0, err
	}

	// 2. Update the account balance atomically
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, tx.AccountID, delta); err != nil {
		return models.Transaction{}, 0, fmt.Errorf("updating balance: %w", err)
	}

	// 3. Commit both operations
	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, 0, fmt.Errorf("committing transaction: %w", err)
	}

	// Fetch the updated balance to return to the caller
	acc, err := s.accRepo.GetByID(ctx, tx.AccountID)
	if err != nil {
		return created, 0, nil // transaction succeeded, just can't return balance
	}

	return created, acc.CurrentBalance, nil
}

// CreateTransfer creates a transfer between two accounts (same currency).
// Creates two linked transactions: debit from source, credit to destination.
// Both accounts' balances are updated atomically.
//
// This is a complex atomic operation — 6 steps inside one DB transaction:
//   1. Create debit transaction (money leaves source)
//   2. Create credit transaction (money enters destination)
//   3. Link the two transactions via linked_transaction_id
//   4. Update source account balance (-amount)
//   5. Update destination account balance (+amount)
//   6. Commit — if any step fails, all 5 previous steps are rolled back
//
// In Laravel: DB::transaction(function() { /* all 6 steps */ });
// In Django: with transaction.atomic(): # all 6 steps
func (s *TransactionService) CreateTransfer(ctx context.Context, sourceAccountID, destAccountID string, amount float64, currency models.Currency, note *string, date time.Time) (models.Transaction, models.Transaction, error) {
	if amount <= 0 {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("amount must be positive")
	}
	if sourceAccountID == "" || destAccountID == "" {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("both source and destination account_id required")
	}
	if sourceAccountID == destAccountID {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("cannot transfer to the same account")
	}

	// Verify same currency
	srcAcc, err := s.accRepo.GetByID(ctx, sourceAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("source account not found: %w", err)
	}
	destAcc, err := s.accRepo.GetByID(ctx, destAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("destination account not found: %w", err)
	}
	if srcAcc.Currency != destAcc.Currency {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("transfer requires same currency; use exchange for cross-currency")
	}

	if date.IsZero() {
		date = time.Now()
	}

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Create debit leg (source)
	debit := models.Transaction{
		Type:             models.TransactionTypeTransfer,
		Amount:           amount,
		Currency:         currency,
		AccountID:        sourceAccountID,
		CounterAccountID: &destAccountID,
		Note:             note,
		Date:             date,
		BalanceDelta:     -amount,
	}
	createdDebit, err := s.txRepo.CreateTx(ctx, dbTx, debit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating debit: %w", err)
	}

	// Create credit leg (destination)
	credit := models.Transaction{
		Type:             models.TransactionTypeTransfer,
		Amount:           amount,
		Currency:         currency,
		AccountID:        destAccountID,
		CounterAccountID: &sourceAccountID,
		Note:             note,
		Date:             date,
		BalanceDelta:     amount,
	}
	createdCredit, err := s.txRepo.CreateTx(ctx, dbTx, credit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating credit: %w", err)
	}

	// Link the two transactions
	if err := s.txRepo.LinkTransactionsTx(ctx, dbTx, createdDebit.ID, createdCredit.ID); err != nil {
		return models.Transaction{}, models.Transaction{}, err
	}

	// Update balances: source loses, destination gains
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, sourceAccountID, -amount); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("debiting source: %w", err)
	}
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, destAccountID, amount); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("crediting destination: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("committing: %w", err)
	}

	// Set linked IDs on the returned structs (DB was updated by LinkTransactionsTx)
	createdDebit.LinkedTransactionID = &createdCredit.ID
	createdCredit.LinkedTransactionID = &createdDebit.ID

	return createdDebit, createdCredit, nil
}

// ExchangeParams holds the parameters for a currency exchange.
// Any two of Amount, Rate, CounterAmount must be provided; the third is auto-calculated.
//
// Uses pointer fields (*float64) to distinguish "not provided" (nil) from "provided as 0".
// This is a common Go pattern for optional parameters. In Laravel, you'd use nullable
// form fields. In Django, Optional[float] or None.
type ExchangeParams struct {
	SourceAccountID string
	DestAccountID   string
	Amount          *float64 // source amount (e.g., USD)
	Rate            *float64 // exchange rate (e.g., 50.5 EGP per USD)
	CounterAmount   *float64 // destination amount (e.g., EGP)
	Note            *string
	Date            time.Time
}

// CreateExchange creates a currency exchange between two accounts in different currencies.
// Creates two linked transactions (debit in source currency, credit in dest currency).
// Logs the exchange rate.
func (s *TransactionService) CreateExchange(ctx context.Context, p ExchangeParams) (models.Transaction, models.Transaction, error) {
	if p.SourceAccountID == "" || p.DestAccountID == "" {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("both source and destination account_id required")
	}
	if p.SourceAccountID == p.DestAccountID {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("cannot exchange to the same account")
	}

	// Verify different currencies
	srcAcc, err := s.accRepo.GetByID(ctx, p.SourceAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("source account not found: %w", err)
	}
	destAcc, err := s.accRepo.GetByID(ctx, p.DestAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("destination account not found: %w", err)
	}
	if srcAcc.Currency == destAcc.Currency {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("exchange requires different currencies; use transfer for same currency")
	}

	// The user-entered rate always means "EGP per 1 USD" regardless of direction.
	// resolveExchangeFields uses: amount * rate = counterAmount (rate = dest/source).
	// When source=EGP, dest=USD: dest/source = USD/EGP = 1/50, so we invert the
	// user rate before resolving and invert back afterward for display/logging.
	sourceIsEGP := srcAcc.Currency == models.CurrencyEGP
	if sourceIsEGP && p.Rate != nil && *p.Rate > 0 {
		inverted := 1.0 / *p.Rate
		p.Rate = &inverted
	}

	// Auto-calculate the missing field from the other two
	amount, formulaRate, counterAmount, err := resolveExchangeFields(p.Amount, p.Rate, p.CounterAmount)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, err
	}

	// Derive the display rate (always EGP per 1 USD) for logging and storage.
	// When source=USD: formulaRate = EGP/USD (already correct).
	// When source=EGP: formulaRate = USD/EGP, so invert to get EGP/USD.
	displayRate := formulaRate
	if sourceIsEGP {
		displayRate = 1.0 / formulaRate
	}

	if p.Date.IsZero() {
		p.Date = time.Now()
	}

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Debit leg (source currency, e.g., USD out)
	debit := models.Transaction{
		Type:             models.TransactionTypeExchange,
		Amount:           amount,
		Currency:         srcAcc.Currency,
		AccountID:        p.SourceAccountID,
		CounterAccountID: &p.DestAccountID,
		ExchangeRate:     &displayRate,
		CounterAmount:    &counterAmount,
		Note:             p.Note,
		Date:             p.Date,
		BalanceDelta:     -amount,
	}
	createdDebit, err := s.txRepo.CreateTx(ctx, dbTx, debit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating debit: %w", err)
	}

	// Credit leg (dest currency, e.g., EGP in)
	credit := models.Transaction{
		Type:             models.TransactionTypeExchange,
		Amount:           counterAmount,
		Currency:         destAcc.Currency,
		AccountID:        p.DestAccountID,
		CounterAccountID: &p.SourceAccountID,
		ExchangeRate:     &displayRate,
		CounterAmount:    &amount,
		Note:             p.Note,
		Date:             p.Date,
		BalanceDelta:     counterAmount,
	}
	createdCredit, err := s.txRepo.CreateTx(ctx, dbTx, credit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating credit: %w", err)
	}

	// Link them
	if err := s.txRepo.LinkTransactionsTx(ctx, dbTx, createdDebit.ID, createdCredit.ID); err != nil {
		return models.Transaction{}, models.Transaction{}, err
	}

	// Update balances
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, p.SourceAccountID, -amount); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("debiting source: %w", err)
	}
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, p.DestAccountID, counterAmount); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("crediting destination: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("committing: %w", err)
	}

	// Log the exchange rate as EGP per 1 USD (non-critical, don't fail if it errors)
	if s.rateRepo != nil {
		source := fmt.Sprintf("%s/%s", srcAcc.Currency, destAcc.Currency)
		s.rateRepo.Log(ctx, p.Date, displayRate, &source, p.Note)
	}

	createdDebit.LinkedTransactionID = &createdCredit.ID
	createdCredit.LinkedTransactionID = &createdDebit.ID

	return createdDebit, createdCredit, nil
}

// CalculateInstapayFee computes the InstaPay fee: 0.1% of amount, min 0.5, max 20 EGP.
// This is a pure function (no receiver) — it's stateless and testable in isolation.
// InstaPay is Egypt's real-time payment network (like Venmo/Zelle in the US).
func CalculateInstapayFee(amount float64) float64 {
	fee := amount * 0.001
	if fee < 0.5 {
		fee = 0.5
	}
	if fee > 20 {
		fee = 20
	}
	return fee
}

// CreateInstapayTransfer creates a transfer with an automatic InstaPay fee.
// The fee is a separate expense transaction (category: Fees & Charges) on the source account.
func (s *TransactionService) CreateInstapayTransfer(ctx context.Context, sourceAccountID, destAccountID string, amount float64, currency models.Currency, note *string, date time.Time, feesCategoryID string) (models.Transaction, models.Transaction, float64, error) {
	if amount <= 0 {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("amount must be positive")
	}
	if sourceAccountID == "" || destAccountID == "" {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("both source and destination account_id required")
	}
	if sourceAccountID == destAccountID {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("cannot transfer to the same account")
	}

	fee := CalculateInstapayFee(amount)

	if date.IsZero() {
		date = time.Now()
	}

	// Verify same currency
	srcAcc, err := s.accRepo.GetByID(ctx, sourceAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("source account not found: %w", err)
	}
	destAcc, err := s.accRepo.GetByID(ctx, destAccountID)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("destination account not found: %w", err)
	}
	if srcAcc.Currency != destAcc.Currency {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("InstaPay requires same currency")
	}

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Debit leg (source)
	instapayNote := "InstaPay transfer"
	if note != nil && *note != "" {
		instapayNote = *note + " (InstaPay)"
	}
	debit := models.Transaction{
		Type:             models.TransactionTypeTransfer,
		Amount:           amount,
		Currency:         currency,
		AccountID:        sourceAccountID,
		CounterAccountID: &destAccountID,
		Note:             &instapayNote,
		FeeAmount:        &fee,
		Date:             date,
	}
	createdDebit, err := s.txRepo.CreateTx(ctx, dbTx, debit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("creating debit: %w", err)
	}

	// Credit leg (destination)
	credit := models.Transaction{
		Type:             models.TransactionTypeTransfer,
		Amount:           amount,
		Currency:         currency,
		AccountID:        destAccountID,
		CounterAccountID: &sourceAccountID,
		Note:             &instapayNote,
		Date:             date,
	}
	createdCredit, err := s.txRepo.CreateTx(ctx, dbTx, credit)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("creating credit: %w", err)
	}

	// Link the two legs
	if err := s.txRepo.LinkTransactionsTx(ctx, dbTx, createdDebit.ID, createdCredit.ID); err != nil {
		return models.Transaction{}, models.Transaction{}, 0, err
	}

	// Fee transaction (separate expense on source account)
	feeNote := "InstaPay fee"
	feeTx := models.Transaction{
		Type:      models.TransactionTypeExpense,
		Amount:    fee,
		Currency:  currency,
		AccountID: sourceAccountID,
		Note:      &feeNote,
		Date:      date,
	}
	if feesCategoryID != "" {
		feeTx.CategoryID = &feesCategoryID
	}
	_, err = s.txRepo.CreateTx(ctx, dbTx, feeTx)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("creating fee: %w", err)
	}

	// Update balances: source loses amount + fee, destination gains amount
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, sourceAccountID, -(amount + fee)); err != nil {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("debiting source: %w", err)
	}
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, destAccountID, amount); err != nil {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("crediting destination: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, models.Transaction{}, 0, fmt.Errorf("committing: %w", err)
	}

	createdDebit.LinkedTransactionID = &createdCredit.ID
	createdCredit.LinkedTransactionID = &createdDebit.ID

	return createdDebit, createdCredit, fee, nil
}

// CreateFawryCashout implements the Fawry credit card cash-out pattern (S-1):
// 1. Charge credit card: expense of (amount + fee)
// 2. Credit Fawry prepaid account: income of amount
// All within a single DB transaction for atomicity.
//
// This is commonly used in Egypt to convert credit card balance to cash
// through Fawry prepaid services.
func (s *TransactionService) CreateFawryCashout(ctx context.Context, creditCardID, prepaidAccountID string, amount, fee float64, currency models.Currency, note *string, date time.Time, feesCategoryID string) (models.Transaction, models.Transaction, error) {
	if amount <= 0 {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("amount must be positive")
	}
	if fee < 0 {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("fee cannot be negative")
	}
	if creditCardID == "" || prepaidAccountID == "" {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("both credit card and prepaid account IDs are required")
	}
	if creditCardID == prepaidAccountID {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("credit card and prepaid account must be different")
	}

	if date.IsZero() {
		date = time.Now()
	}

	totalCharge := amount + fee

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// 1. Credit card charge (expense: amount + fee)
	chargeNote := "Fawry cash-out"
	if note != nil && *note != "" {
		chargeNote = *note + " (Fawry cash-out)"
	}
	chargeTx := models.Transaction{
		Type:             models.TransactionTypeExpense,
		Amount:           totalCharge,
		Currency:         currency,
		AccountID:        creditCardID,
		CounterAccountID: &prepaidAccountID,
		FeeAmount:        &fee,
		Note:             &chargeNote,
		Date:             date,
	}
	if feesCategoryID != "" {
		chargeTx.CategoryID = &feesCategoryID
	}
	createdCharge, err := s.txRepo.CreateTx(ctx, dbTx, chargeTx)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating charge: %w", err)
	}

	// 2. Prepaid account credit (income: net amount)
	creditNote := "Fawry top-up"
	if note != nil && *note != "" {
		creditNote = *note + " (Fawry top-up)"
	}
	creditTx := models.Transaction{
		Type:             models.TransactionTypeIncome,
		Amount:           amount,
		Currency:         currency,
		AccountID:        prepaidAccountID,
		CounterAccountID: &creditCardID,
		Note:             &creditNote,
		Date:             date,
	}
	createdCredit, err := s.txRepo.CreateTx(ctx, dbTx, creditTx)
	if err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("creating credit: %w", err)
	}

	// Link the two transactions
	if err := s.txRepo.LinkTransactionsTx(ctx, dbTx, createdCharge.ID, createdCredit.ID); err != nil {
		return models.Transaction{}, models.Transaction{}, err
	}

	// Update balances: credit card goes down by total, prepaid goes up by net amount
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, creditCardID, -totalCharge); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("debiting credit card: %w", err)
	}
	if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, prepaidAccountID, amount); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("crediting prepaid: %w", err)
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, models.Transaction{}, fmt.Errorf("committing: %w", err)
	}

	createdCharge.LinkedTransactionID = &createdCredit.ID
	createdCredit.LinkedTransactionID = &createdCharge.ID

	return createdCharge, createdCredit, nil
}

// resolveExchangeFields computes the missing field from two provided values.
// amount * rate = counterAmount
//
// This is a private (unexported) function — lowercase name means it's only
// visible within the `service` package. Like PHP's private methods or Python's
// _leading_underscore convention (but enforced by the compiler, not just convention).
func resolveExchangeFields(amount, rate, counterAmount *float64) (float64, float64, float64, error) {
	count := 0
	if amount != nil && *amount > 0 {
		count++
	}
	if rate != nil && *rate > 0 {
		count++
	}
	if counterAmount != nil && *counterAmount > 0 {
		count++
	}
	if count < 2 {
		return 0, 0, 0, fmt.Errorf("provide at least two of: amount, rate, counter_amount")
	}

	if amount != nil && rate != nil && *amount > 0 && *rate > 0 {
		return *amount, *rate, *amount * *rate, nil
	}
	if amount != nil && counterAmount != nil && *amount > 0 && *counterAmount > 0 {
		return *amount, *counterAmount / *amount, *counterAmount, nil
	}
	if rate != nil && counterAmount != nil && *rate > 0 && *counterAmount > 0 {
		return *counterAmount / *rate, *rate, *counterAmount, nil
	}
	return 0, 0, 0, fmt.Errorf("invalid exchange parameters")
}

// Update modifies a transaction and recalculates the balance delta.
// The balance adjustment is: reverse old delta + apply new delta.
//
// This shows a key pattern: to update a financial record, we must:
//   1. Load the old record (to know the previous balance impact)
//   2. Compute the difference: newDelta - oldDelta
//   3. Apply the net change to the account balance
//
// All inside a DB transaction for atomicity.
func (s *TransactionService) Update(ctx context.Context, updated models.Transaction) (models.Transaction, float64, error) {
	if err := s.validateBasic(updated); err != nil {
		return models.Transaction{}, 0, err
	}

	// Get the old transaction to calculate the balance diff
	old, err := s.txRepo.GetByID(ctx, updated.ID)
	if err != nil {
		return models.Transaction{}, 0, err
	}

	oldDelta := s.balanceDelta(old)
	newDelta := s.balanceDelta(updated)
	balanceAdjustment := newDelta - oldDelta // net change to apply

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return models.Transaction{}, 0, fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	result, err := s.txRepo.UpdateTx(ctx, dbTx, updated)
	if err != nil {
		return models.Transaction{}, 0, err
	}

	if balanceAdjustment != 0 {
		if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, old.AccountID, balanceAdjustment); err != nil {
			return models.Transaction{}, 0, fmt.Errorf("adjusting balance: %w", err)
		}
	}

	if err := dbTx.Commit(); err != nil {
		return models.Transaction{}, 0, fmt.Errorf("committing: %w", err)
	}

	acc, err := s.accRepo.GetByID(ctx, old.AccountID)
	if err != nil {
		return result, 0, nil
	}
	return result, acc.CurrentBalance, nil
}

// Delete removes a transaction and reverses its balance impact.
// For linked transactions (transfers/exchanges), both legs are deleted.
//
// This is the inverse of Create: it undoes the balance change. For transfers,
// it must also find and delete the linked (counterpart) transaction and reverse
// both account balances. All within a single DB transaction.
func (s *TransactionService) Delete(ctx context.Context, id string) error {
	tx, err := s.txRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	dbTx, err := s.txRepo.BeginTx(ctx)
	if err != nil {
		return fmt.Errorf("beginning transaction: %w", err)
	}
	defer dbTx.Rollback()

	// Delete this transaction
	if err := s.txRepo.DeleteTx(ctx, dbTx, id); err != nil {
		return err
	}

	isLinked := tx.LinkedTransactionID != nil && *tx.LinkedTransactionID != ""

	if isLinked {
		// Transfer/exchange: this leg's account was debited, linked leg's was credited.
		// Reverse: add amount back to this account, subtract from linked account.
		if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, tx.AccountID, tx.Amount); err != nil {
			return fmt.Errorf("reversing balance: %w", err)
		}

		linked, err := s.txRepo.GetByID(ctx, *tx.LinkedTransactionID)
		if err == nil {
			if err := s.txRepo.DeleteTx(ctx, dbTx, linked.ID); err != nil {
				return fmt.Errorf("deleting linked: %w", err)
			}
			if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, linked.AccountID, -linked.Amount); err != nil {
				return fmt.Errorf("reversing linked balance: %w", err)
			}
		}
	} else {
		// Simple expense/income reversal
		reverseDelta := -s.balanceDelta(tx)
		if err := s.txRepo.UpdateBalanceTx(ctx, dbTx, tx.AccountID, reverseDelta); err != nil {
			return fmt.Errorf("reversing balance: %w", err)
		}
	}

	return dbTx.Commit()
}

func (s *TransactionService) GetByID(ctx context.Context, id string) (models.Transaction, error) {
	return s.txRepo.GetByID(ctx, id)
}

func (s *TransactionService) GetRecent(ctx context.Context, limit int) ([]models.Transaction, error) {
	if limit <= 0 {
		limit = 15
	}
	return s.txRepo.GetRecent(ctx, limit)
}

func (s *TransactionService) GetByAccount(ctx context.Context, accountID string, limit int) ([]models.Transaction, error) {
	if limit <= 0 {
		limit = 50
	}
	return s.txRepo.GetByAccount(ctx, accountID, limit)
}

// balanceDelta calculates how a transaction affects its account's balance.
// For expense/income only. Transfer/exchange deltas are handled directly
// in CreateTransfer/Delete since they involve two accounts.
//
// This is a method with a pointer receiver: (s *TransactionService).
// In Go, methods on pointer receivers can modify the struct (though this one doesn't).
// The convention is: if any method needs a pointer receiver, all methods should use one.
// Think of (s *TransactionService) as $this in PHP or self in Python.
// See: https://go.dev/tour/methods/4
func (s *TransactionService) balanceDelta(tx models.Transaction) float64 {
	switch tx.Type {
	case models.TransactionTypeExpense:
		return -tx.Amount
	case models.TransactionTypeIncome:
		return tx.Amount
	default:
		return 0 // transfers/exchanges handle their own deltas
	}
}

// GetFiltered retrieves transactions matching the given filters.
func (s *TransactionService) GetFiltered(ctx context.Context, f repository.TransactionFilter) ([]models.Transaction, error) {
	if f.Limit <= 0 {
		f.Limit = 50
	}
	return s.txRepo.GetFiltered(ctx, f)
}

// SmartDefaults holds pre-computed defaults for the transaction entry form.
// Pre-selects last-used account, sorts categories by frequency, and auto-selects
// a category if it was used 3+ times consecutively.
//
// This is a DTO (Data Transfer Object) — a plain struct with no methods. It bundles
// related data for the handler/template layer. In Laravel, you'd use a resource
// or plain array. In Django, a dictionary or dataclass.
type SmartDefaults struct {
	LastAccountID       string   // pre-select this account
	AutoCategoryID      string   // auto-select if 3+ consecutive uses
	RecentCategoryIDs   []string // ordered by frequency for sorting
}

// GetSmartDefaults computes smart defaults for the entry form based on history.
func (s *TransactionService) GetSmartDefaults(ctx context.Context, txType string) SmartDefaults {
	defaults := SmartDefaults{}

	if lastAcc, err := s.txRepo.GetLastUsedAccountID(ctx); err == nil {
		defaults.LastAccountID = lastAcc
	}

	if recentCats, err := s.txRepo.GetRecentCategoryIDs(ctx, txType, 20); err == nil {
		defaults.RecentCategoryIDs = recentCats
	}

	if autoCat, err := s.txRepo.GetConsecutiveCategoryID(ctx, txType, 3); err == nil {
		defaults.AutoCategoryID = autoCat
	}

	return defaults
}

// GetByAccountDateRange returns transactions for an account within a date range.
// Used by credit card statement view (TASK-071).
func (s *TransactionService) GetByAccountDateRange(ctx context.Context, accountID string, from, to time.Time) ([]models.Transaction, error) {
	return s.txRepo.GetByAccountDateRange(ctx, accountID, from, to)
}

// GetPaymentsToAccount returns income/transfer payments that credit a specific account.
// Used by credit card payment history (TASK-075).
func (s *TransactionService) GetPaymentsToAccount(ctx context.Context, accountID string, limit int) ([]models.Transaction, error) {
	return s.txRepo.GetPaymentsToAccount(ctx, accountID, limit)
}

// SuggestCategory returns the most likely category ID based on note keywords (TASK-079).
// Uses historical transaction data to suggest a category when the user types a note.
func (s *TransactionService) SuggestCategory(ctx context.Context, noteKeyword string) string {
	return s.txRepo.SuggestCategory(ctx, noteKeyword)
}

// validateBasic performs basic field validation on a transaction.
// Private method (lowercase) — only callable from within this package.
// In Laravel, this would be in a FormRequest or a private validate() method.
// In Django, this would be in the model's clean() method or serializer validation.
func (s *TransactionService) validateBasic(tx models.Transaction) error {
	if tx.Amount <= 0 {
		return fmt.Errorf("amount must be positive")
	}
	if tx.AccountID == "" {
		return fmt.Errorf("account_id is required")
	}
	if tx.Type == "" {
		return fmt.Errorf("transaction type is required")
	}
	if tx.Currency == "" {
		return fmt.Errorf("currency is required")
	}
	return nil
}
