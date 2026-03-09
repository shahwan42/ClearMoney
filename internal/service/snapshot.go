// Package service — SnapshotService manages daily balance snapshots.
//
// Snapshots are like periodic "photos" of your financial state. Without them,
// we only know current balances. With them, we can show:
//   - Net worth sparklines (30-day trend)
//   - Per-account balance sparklines
//   - Month-over-month comparisons
//   - Credit card utilization history
//
// In Laravel terms, this is like a Service class that coordinates between
// the snapshot repository and the account/exchange rate repos.
// In Django, similar to a service module that orchestrates model operations.
package service

import (
	"context"
	"log"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

// SnapshotService manages creation and retrieval of daily balance snapshots.
type SnapshotService struct {
	snapshotRepo     *repository.SnapshotRepo
	accountRepo      *repository.AccountRepo
	institutionRepo  *repository.InstitutionRepo
	exchangeRateRepo *repository.ExchangeRateRepo
}

// NewSnapshotService creates a SnapshotService with required dependencies.
func NewSnapshotService(
	snapshotRepo *repository.SnapshotRepo,
	accountRepo *repository.AccountRepo,
	institutionRepo *repository.InstitutionRepo,
	exchangeRateRepo *repository.ExchangeRateRepo,
) *SnapshotService {
	return &SnapshotService{
		snapshotRepo:     snapshotRepo,
		accountRepo:      accountRepo,
		institutionRepo:  institutionRepo,
		exchangeRateRepo: exchangeRateRepo,
	}
}

// TakeSnapshot captures today's financial state as a daily snapshot.
// Safe to call multiple times (UPSERT semantics).
//
// Steps:
// 1. Get all accounts and sum balances for net worth
// 2. Convert USD balances to EGP using latest exchange rate
// 3. Store daily snapshot (net worth, spending, income)
// 4. Store per-account snapshots
func (s *SnapshotService) TakeSnapshot(ctx context.Context) error {
	today := time.Now().Truncate(24 * time.Hour)
	return s.takeSnapshotForDate(ctx, today, true)
}

// takeSnapshotForDate captures the financial state for a specific date.
// If useCurrentBalances is true, uses accounts' current_balance.
// If false, computes historical balances by subtracting future balance_deltas.
func (s *SnapshotService) takeSnapshotForDate(ctx context.Context, date time.Time, useCurrentBalances bool) error {
	// Get all institutions and their accounts
	institutions, err := s.institutionRepo.GetAll(ctx)
	if err != nil {
		return err
	}

	var netWorthRaw, usdTotal float64
	type accountBalance struct {
		ID      string
		Balance float64
	}
	var accountBalances []accountBalance

	for _, inst := range institutions {
		accounts, err := s.accountRepo.GetByInstitution(ctx, inst.ID)
		if err != nil {
			continue
		}
		for _, acc := range accounts {
			balance := acc.CurrentBalance
			if !useCurrentBalances {
				// Historical balance: current_balance minus future transactions
				futureDeltas, err := s.snapshotRepo.GetBalanceDeltaAfterDate(ctx, acc.ID, date)
				if err != nil {
					log.Printf("snapshot: error computing historical balance for %s: %v", acc.Name, err)
					continue
				}
				balance = acc.CurrentBalance - futureDeltas
			}
			netWorthRaw += balance
			if acc.Currency == models.CurrencyUSD {
				usdTotal += balance
			}
			accountBalances = append(accountBalances, accountBalance{ID: acc.ID, Balance: balance})
		}
	}

	// Get exchange rate for USD → EGP conversion
	var exchangeRate, netWorthEGP float64
	if s.exchangeRateRepo != nil {
		if rate, err := s.exchangeRateRepo.GetLatest(ctx); err == nil && rate > 0 {
			exchangeRate = rate
			netWorthEGP = (netWorthRaw - usdTotal) + (usdTotal * rate)
		}
	}
	if netWorthEGP == 0 {
		netWorthEGP = netWorthRaw
	}

	// Get daily spending and income for this date
	spending, _ := s.snapshotRepo.GetDailySpending(ctx, date)
	income, _ := s.snapshotRepo.GetDailyIncome(ctx, date)

	// Upsert daily snapshot
	err = s.snapshotRepo.UpsertDaily(ctx, models.DailySnapshot{
		Date:          date,
		NetWorthEGP:   netWorthEGP,
		NetWorthRaw:   netWorthRaw,
		ExchangeRate:  exchangeRate,
		DailySpending: spending,
		DailyIncome:   income,
	})
	if err != nil {
		return err
	}

	// Upsert per-account snapshots
	for _, ab := range accountBalances {
		if err := s.snapshotRepo.UpsertAccount(ctx, models.AccountSnapshot{
			Date:      date,
			AccountID: ab.ID,
			Balance:   ab.Balance,
		}); err != nil {
			log.Printf("snapshot: error saving account snapshot for %s: %v", ab.ID, err)
		}
	}

	return nil
}

// BackfillSnapshots fills in missing daily snapshots for the last N days.
// Historical balances are computed by subtracting future transaction deltas
// from the current balance: balance_on_date = current_balance - SUM(delta after date).
//
// This is called on startup so sparklines have data even on first run.
func (s *SnapshotService) BackfillSnapshots(ctx context.Context, days int) (int, error) {
	today := time.Now().Truncate(24 * time.Hour)
	count := 0

	for i := days; i >= 0; i-- {
		date := today.AddDate(0, 0, -i)
		exists, err := s.snapshotRepo.Exists(ctx, date)
		if err != nil {
			log.Printf("snapshot: error checking date %s: %v", date.Format("2006-01-02"), err)
			continue
		}
		if exists {
			continue
		}

		// Use current balances for today, historical calculation for past dates
		useCurrentBalances := i == 0
		if err := s.takeSnapshotForDate(ctx, date, useCurrentBalances); err != nil {
			log.Printf("snapshot: error backfilling %s: %v", date.Format("2006-01-02"), err)
			continue
		}
		count++
	}

	return count, nil
}

// GetNetWorthHistory returns daily net worth values for the last N days.
// Returns a slice of float64 values suitable for sparklinePoints().
func (s *SnapshotService) GetNetWorthHistory(ctx context.Context, days int) ([]float64, error) {
	from := time.Now().AddDate(0, 0, -days).Truncate(24 * time.Hour)
	to := time.Now().Truncate(24 * time.Hour)

	snapshots, err := s.snapshotRepo.GetDailyRange(ctx, from, to)
	if err != nil {
		return nil, err
	}

	values := make([]float64, 0, len(snapshots))
	for _, snap := range snapshots {
		values = append(values, snap.NetWorthEGP)
	}
	return values, nil
}

// GetAccountHistory returns daily balances for a specific account over N days.
// Returns a slice of float64 values suitable for sparklinePoints().
func (s *SnapshotService) GetAccountHistory(ctx context.Context, accountID string, days int) ([]float64, error) {
	from := time.Now().AddDate(0, 0, -days).Truncate(24 * time.Hour)
	to := time.Now().Truncate(24 * time.Hour)

	snapshots, err := s.snapshotRepo.GetAccountRange(ctx, accountID, from, to)
	if err != nil {
		return nil, err
	}

	values := make([]float64, 0, len(snapshots))
	for _, snap := range snapshots {
		values = append(values, snap.Balance)
	}
	return values, nil
}

// GetDailySnapshots returns full daily snapshot records for a date range.
// Useful for month-over-month comparisons that need spending/income data.
func (s *SnapshotService) GetDailySnapshots(ctx context.Context, from, to time.Time) ([]models.DailySnapshot, error) {
	return s.snapshotRepo.GetDailyRange(ctx, from, to)
}
