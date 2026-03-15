// Package jobs — snapshot.go runs the daily balance snapshot job on startup.
//
// # The Snapshot Pattern
//
// A snapshot captures a "photograph" of your financial state (account balances,
// net worth) at a specific point in time and stores it for historical tracking.
// Without daily snapshots, we'd have no data for:
//   - Balance sparklines on the dashboard and account cards
//   - Net worth trend indicators (up/down arrows)
//   - Historical balance comparisons ("your net worth 30 days ago was...")
//
// # Why Snapshots Instead of Computing on the Fly?
//
// We could compute historical balances by replaying transactions backwards, but
// that gets expensive with thousands of transactions. Snapshots trade storage
// for speed — each day's state is pre-computed and stored in two tables:
//   - daily_snapshots:   one row per day with total net worth
//   - account_snapshots: one row per account per day with individual balances
//
// This is similar to:
//   - Laravel: A scheduled command that runs daily via `$schedule->daily()`
//     and populates a `daily_snapshots` table using an Artisan command
//   - Django:  A management command (python manage.py take_snapshots) that
//     could be scheduled via cron or Celery Beat
//
// # UPSERT Semantics (INSERT ... ON CONFLICT UPDATE)
//
// The snapshot service uses PostgreSQL's UPSERT (INSERT ... ON CONFLICT DO UPDATE)
// to make snapshots idempotent. This means:
//   - First call for a date:  INSERTs a new snapshot row
//   - Subsequent calls:       UPDATEs the existing row with fresh data
//
// This makes it safe to call TakeSnapshots on every server startup without
// creating duplicates. In Laravel, you'd achieve this with updateOrCreate().
// In Django, it's update_or_create().
//
// Called from main.go during startup, after reconciliation completes.
package jobs

import (
	"context"
	"database/sql"
	"log/slog"

	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/service"
)

// TakeSnapshots runs the snapshot job: takes today's snapshot and backfills
// any missing days (up to 90 days back). Safe to call on every startup
// thanks to UPSERT semantics — existing snapshots are updated, not duplicated.
//
// Returns the number of days backfilled (0 if all were already present).
//
// # Manual Dependency Wiring
//
// Go doesn't have a built-in DI container like Laravel's service container
// or Django's app registry. Instead, we manually create repositories and inject
// them into the service. This is "poor man's DI" — explicit and simple.
//
// In Laravel, this would be handled by the service container:
//
//	$snapshotSvc = app(SnapshotService::class); // auto-resolves dependencies
//
// In Django, you'd import the service directly or use dependency-injector.
// In Go, you wire it up explicitly — more typing, but no "magic" to debug.
func TakeSnapshots(ctx context.Context, db *sql.DB) (int, error) {
	// Wire up the snapshot service with its dependencies.
	// Each repository wraps *sql.DB with typed query methods (like Laravel
	// repositories or Django managers). The service orchestrates them.
	snapshotRepo := repository.NewSnapshotRepo(db)
	accountRepo := repository.NewAccountRepo(db)
	institutionRepo := repository.NewInstitutionRepo(db)
	exchangeRateRepo := repository.NewExchangeRateRepo(db)

	snapshotSvc := service.NewSnapshotService(snapshotRepo, accountRepo, institutionRepo, exchangeRateRepo)

	// Take today's snapshot first (uses current balances, most accurate).
	// We log the error but continue to backfill — partial success is better
	// than total failure. This is a resilience pattern: don't let one failure
	// prevent other useful work from completing.
	if err := snapshotSvc.TakeSnapshot(ctx); err != nil {
		slog.Error("snapshot: error taking today's snapshot", "error", err)
		// Continue to backfill even if today fails
	}

	// Backfill missing days (up to 90 days back).
	// Historical balances are approximated by subtracting future transactions
	// from the current balance. This gives a reasonable estimate even though
	// we don't know the exact balance at each past date.
	//
	// The backfill is idempotent — already-existing snapshots are updated
	// (via UPSERT), so running this multiple times is safe.
	backfilled, err := snapshotSvc.BackfillSnapshots(ctx, 90)
	if err != nil {
		return backfilled, err
	}

	return backfilled, nil
}
