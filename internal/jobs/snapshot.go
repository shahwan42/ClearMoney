// Package jobs — snapshot.go runs the daily balance snapshot job on startup.
//
// This job captures a "photograph" of your financial state (account balances,
// net worth) and stores it for historical tracking. Without it, sparklines
// and trend indicators would have no data.
//
// Called from main.go during startup, after reconciliation.
// Similar to a Laravel scheduled command (php artisan schedule:run)
// or a Django management command that runs daily.
package jobs

import (
	"context"
	"database/sql"
	"log/slog"

	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
	"github.com/ahmedelsamadisi/clearmoney/internal/service"
)

// TakeSnapshots runs the snapshot job: takes today's snapshot and backfills
// any missing days (up to 90 days back). Safe to call on every startup
// thanks to UPSERT semantics — existing snapshots are updated, not duplicated.
//
// Returns the number of days backfilled (0 if all were already present).
func TakeSnapshots(ctx context.Context, db *sql.DB) (int, error) {
	// Wire up the snapshot service with its dependencies
	snapshotRepo := repository.NewSnapshotRepo(db)
	accountRepo := repository.NewAccountRepo(db)
	institutionRepo := repository.NewInstitutionRepo(db)
	exchangeRateRepo := repository.NewExchangeRateRepo(db)

	snapshotSvc := service.NewSnapshotService(snapshotRepo, accountRepo, institutionRepo, exchangeRateRepo)

	// Take today's snapshot first (uses current balances, most accurate)
	if err := snapshotSvc.TakeSnapshot(ctx); err != nil {
		slog.Error("snapshot: error taking today's snapshot", "error", err)
		// Continue to backfill even if today fails
	}

	// Backfill missing days (up to 90 days back).
	// Historical balances are approximated by subtracting future transactions.
	backfilled, err := snapshotSvc.BackfillSnapshots(ctx, 90)
	if err != nil {
		return backfilled, err
	}

	return backfilled, nil
}
