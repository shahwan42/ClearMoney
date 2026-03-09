// Reconcile command — verifies and optionally fixes account balances.
// Usage: make reconcile         (report only)
//        make reconcile-fix     (auto-fix discrepancies)
package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"

	"github.com/ahmedelsamadisi/clearmoney/internal/database"
	"github.com/ahmedelsamadisi/clearmoney/internal/jobs"
)

func main() {
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		slog.Error("DATABASE_URL is required")
		os.Exit(1)
	}

	db, err := database.Connect(url)
	if err != nil {
		slog.Error("database connection failed", "error", err)
		os.Exit(1)
	}
	defer db.Close()

	if err := database.RunMigrations(db); err != nil {
		slog.Error("migrations failed", "error", err)
		os.Exit(1)
	}

	autoFix := len(os.Args) > 1 && os.Args[1] == "--fix"

	discrepancies, err := jobs.ReconcileBalances(context.Background(), db, autoFix)
	if err != nil {
		slog.Error("reconciliation failed", "error", err)
		os.Exit(1)
	}

	if len(discrepancies) == 0 {
		fmt.Println("All account balances are consistent.")
		return
	}

	fmt.Printf("Found %d discrepancies:\n", len(discrepancies))
	for _, d := range discrepancies {
		fmt.Printf("  %-30s cached=%.2f expected=%.2f diff=%+.2f\n",
			d.AccountName, d.CachedBalance, d.ExpectedBalance, d.Difference)
	}

	if autoFix {
		fmt.Println("Balances have been auto-fixed.")
	} else {
		fmt.Println("Run with --fix to auto-correct.")
	}
}
