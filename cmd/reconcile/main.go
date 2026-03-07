// Reconcile command — verifies and optionally fixes account balances.
// Usage: make reconcile         (report only)
//        make reconcile-fix     (auto-fix discrepancies)
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/ahmedelsamadisi/clearmoney/internal/database"
	"github.com/ahmedelsamadisi/clearmoney/internal/jobs"
)

func main() {
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		log.Fatal("DATABASE_URL is required")
	}

	db, err := database.Connect(url)
	if err != nil {
		log.Fatalf("database: %v", err)
	}
	defer db.Close()

	if err := database.RunMigrations(db); err != nil {
		log.Fatalf("migrations: %v", err)
	}

	autoFix := len(os.Args) > 1 && os.Args[1] == "--fix"

	discrepancies, err := jobs.ReconcileBalances(context.Background(), db, autoFix)
	if err != nil {
		log.Fatalf("reconciliation failed: %v", err)
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
