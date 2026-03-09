package jobs

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
)

// RefreshMaterializedViews refreshes all materialized views concurrently.
// CONCURRENTLY allows reads during refresh (requires a unique index on each view).
// Call this after batch transaction changes or on a schedule.
func RefreshMaterializedViews(ctx context.Context, db *sql.DB) error {
	views := []string{
		"mv_monthly_category_totals",
		"mv_daily_tx_counts",
	}

	for _, view := range views {
		// CONCURRENTLY allows queries while refresh is in progress.
		// Falls back to regular REFRESH if the view has never been populated.
		_, err := db.ExecContext(ctx, fmt.Sprintf("REFRESH MATERIALIZED VIEW CONCURRENTLY %s", view))
		if err != nil {
			slog.Warn("failed to refresh view concurrently, retrying without CONCURRENTLY", "view", view, "error", err)
			// Try without CONCURRENTLY (needed for first population)
			_, err = db.ExecContext(ctx, fmt.Sprintf("REFRESH MATERIALIZED VIEW %s", view))
			if err != nil {
				return fmt.Errorf("refreshing %s: %w", view, err)
			}
		}
	}
	return nil
}
