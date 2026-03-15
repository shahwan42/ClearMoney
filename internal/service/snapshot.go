// Package service — SnapshotService manages daily balance snapshots.
//
// Snapshots are like periodic "photos" of your financial state. Without them,
// we only know current balances. With them, we can show:
//   - Net worth sparklines (30-day trend)
//   - Per-account balance sparklines
//   - Month-over-month comparisons
//   - Credit card utilization history
//
// Laravel analogy: Like a SnapshotService called from a daily scheduled task
// (php artisan snapshots:take in app/Console/Kernel.php). The backfill feature is
// similar to a seeder that populates historical data. In ClearMoney, TakeSnapshot()
// runs on app startup and BackfillSnapshots() fills gaps for the last 30 days.
//
// Django analogy: Like a management command (manage.py take_snapshots) or Celery
// periodic task. The UPSERT semantics (INSERT ... ON CONFLICT UPDATE) make it
// safe to run multiple times — idempotent like Django's get_or_create().
//
// Key Go concepts:
//   - log/slog: Go's structured logger (added in Go 1.21). Like Laravel's Log facade
//     or Python's logging module, but with structured key-value pairs.
//     See: https://pkg.go.dev/log/slog
//   - time.Truncate(24*time.Hour): rounds down to midnight (removes time component).
//     Like Carbon::startOfDay() in Laravel or date.replace(hour=0) in Python.
//     See: https://pkg.go.dev/time#Time.Truncate
package service

import (
	"context"
	"log/slog"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/repository"
)

// SnapshotService manages creation and retrieval of daily balance snapshots.
// This service has 4 dependencies — all required (injected via constructor).
// It reads from accounts and exchange rates, and writes to snapshots.
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
					slog.Error("snapshot: error computing historical balance", "account", acc.Name, "error", err)
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
			slog.Error("snapshot: error saving account snapshot", "account_id", ab.ID, "error", err)
		}
	}

	return nil
}

// BackfillSnapshots fills in missing daily snapshots for the last N days.
// Historical balances are computed by subtracting future transaction deltas
// from the current balance: balance_on_date = current_balance - SUM(delta after date).
//
// This is called on startup so sparklines have data even on first run.
//
// The algorithm: for each missing day, compute what the balance WAS by starting from
// the current balance and subtracting all balance_delta values from transactions after
// that date. This is a reverse-computation approach — we don't need to replay all
// transactions from the beginning.
//
// Idempotency: checks snapshotRepo.Exists() before creating, so calling this
// repeatedly is safe (like Laravel's firstOrCreate or Django's get_or_create).
func (s *SnapshotService) BackfillSnapshots(ctx context.Context, days int) (int, error) {
	today := time.Now().Truncate(24 * time.Hour)
	count := 0

	for i := days; i >= 0; i-- {
		date := today.AddDate(0, 0, -i)
		exists, err := s.snapshotRepo.Exists(ctx, date)
		if err != nil {
			slog.Warn("snapshot: error checking date", "date", date.Format("2006-01-02"), "error", err)
			continue
		}
		if exists {
			continue
		}

		// Use current balances for today, historical calculation for past dates
		useCurrentBalances := i == 0
		if err := s.takeSnapshotForDate(ctx, date, useCurrentBalances); err != nil {
			slog.Warn("snapshot: error backfilling", "date", date.Format("2006-01-02"), "error", err)
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
