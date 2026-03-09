package jobs

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
)

// RefreshMaterializedViews refreshes all PostgreSQL materialized views.
//
// # What Are Materialized Views? (for Laravel/Django developers)
//
// A materialized view is a database-level cached query. Think of it as a database
// table that is automatically populated by a SELECT query, but unlike a regular
// view, the results are stored on disk for fast reads.
//
//   - Regular view:        re-runs the query every time you SELECT from it (slow)
//   - Materialized view:   stores the results; you must REFRESH to update them
//
// In Laravel terms, this is like a cached Eloquent query that you manually
// invalidate. In Django, it's similar to django-cachalot or manually caching
// QuerySet results in Redis, but done at the database level.
//
// Our materialized views:
//   - mv_monthly_category_totals: pre-aggregated monthly spending by category
//     (powers the reports/spending page). Without this, we'd run expensive
//     GROUP BY queries on every page load.
//   - mv_daily_tx_counts: pre-aggregated daily transaction counts
//     (powers the habit/streak tracker on the dashboard).
//
// # CONCURRENTLY vs Regular REFRESH
//
// REFRESH MATERIALIZED VIEW CONCURRENTLY:
//   - Allows reads from the view while it's being refreshed (no downtime)
//   - Requires a UNIQUE INDEX on the materialized view
//   - Cannot be used on the first refresh (the view must have data first)
//
// REFRESH MATERIALIZED VIEW (without CONCURRENTLY):
//   - Locks the view during refresh (reads block until it finishes)
//   - Works always, including the first population
//
// Our strategy: try CONCURRENTLY first, fall back to regular REFRESH.
// This handles both the first-run case and subsequent refreshes gracefully.
//
// # When This Runs
//
// Called from main.go on startup (after migrations and reconciliation).
// Could also be called on a schedule via cron or after batch operations.
//
// See: https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html
// See: https://www.postgresql.org/docs/current/sql-creatematerializedview.html
func RefreshMaterializedViews(ctx context.Context, db *sql.DB) error {
	views := []string{
		"mv_monthly_category_totals",
		"mv_daily_tx_counts",
	}

	for _, view := range views {
		// Try CONCURRENTLY first — allows reads while refreshing.
		// fmt.Sprintf is used here because PostgreSQL doesn't support parameterized
		// DDL statements (you can't use $1 for table/view names). This is safe
		// because the view names are hardcoded strings, not user input.
		_, err := db.ExecContext(ctx, fmt.Sprintf("REFRESH MATERIALIZED VIEW CONCURRENTLY %s", view))
		if err != nil {
			slog.Warn("failed to refresh view concurrently, retrying without CONCURRENTLY", "view", view, "error", err)
			// Fall back to regular REFRESH (needed for first population when
			// the view has never been refreshed and has no data yet).
			_, err = db.ExecContext(ctx, fmt.Sprintf("REFRESH MATERIALIZED VIEW %s", view))
			if err != nil {
				return fmt.Errorf("refreshing %s: %w", view, err)
			}
		}
	}
	return nil
}
