// Package jobs — snapshot.go runs the daily balance snapshot job on startup.
//
// Snapshots capture a "photograph" of each user's financial state (account balances,
// net worth) at a specific point in time. Iterates over all users since accounts
// and balances are user-scoped.
//
// Safe to call on every startup thanks to UPSERT semantics.
// Called from main.go during startup, after reconciliation completes.
package jobs

import (
	"context"
	"database/sql"
	"log/slog"
	"time"

	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/service"
)

// TakeSnapshots runs the snapshot job for all users: takes today's snapshot and
// backfills any missing days (up to 90 days back).
// Returns the total number of days backfilled across all users.
func TakeSnapshots(ctx context.Context, db *sql.DB, loc *time.Location) (int, error) {
	userRepo := repository.NewUserRepo(db)
	snapshotRepo := repository.NewSnapshotRepo(db)
	accountRepo := repository.NewAccountRepo(db)
	institutionRepo := repository.NewInstitutionRepo(db)
	exchangeRateRepo := repository.NewExchangeRateRepo(db)

	snapshotSvc := service.NewSnapshotService(snapshotRepo, accountRepo, institutionRepo, exchangeRateRepo)
	snapshotSvc.SetTimezone(loc)

	userIDs, err := userRepo.GetAllIDs(ctx)
	if err != nil {
		return 0, err
	}

	totalBackfilled := 0
	for _, userID := range userIDs {
		if err := snapshotSvc.TakeSnapshot(ctx, userID); err != nil {
			slog.Error("snapshot: error taking today's snapshot", "user_id", userID, "error", err)
		}

		backfilled, err := snapshotSvc.BackfillSnapshots(ctx, userID, 90)
		if err != nil {
			slog.Warn("snapshot: backfill error", "user_id", userID, "error", err)
		}
		totalBackfilled += backfilled
	}

	return totalBackfilled, nil
}
