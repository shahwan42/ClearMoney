// Reconcile command — verifies and optionally fixes account balances.
//
// This is a standalone CLI binary, similar to a Laravel Artisan command
// (php artisan reconcile:balances) or a Django management command
// (python manage.py reconcile_balances).
//
// In Go, CLI tools live under cmd/ — each subdirectory becomes its own binary.
// Go builds one binary per `package main`, so cmd/server/ and cmd/reconcile/
// are two separate executables compiled from the same codebase.
//
// Usage:
//
//	make reconcile          (report only — shows discrepancies without changing data)
//	make reconcile-fix      (auto-fix — updates cached balances to match transaction sums)
//
// See: https://go.dev/doc/code#Organization — Go project layout conventions
package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"

	"github.com/shahwan42/clearmoney/internal/database"
	"github.com/shahwan42/clearmoney/internal/jobs"
)

func main() {
	// os.Getenv reads an environment variable — returns "" if unset.
	// Unlike Laravel where .env is auto-loaded by Dotenv, Go programs read
	// env vars directly from the OS. The Makefile or docker-compose sets these.
	// See: https://pkg.go.dev/os#Getenv
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

	// Run migrations first to ensure the schema is up-to-date.
	// This is safe because golang-migrate tracks applied migrations in a
	// schema_migrations table (like Laravel's migrations table or Django's
	// django_migrations table) — already-applied migrations are skipped.
	if err := database.RunMigrations(db); err != nil {
		slog.Error("migrations failed", "error", err)
		os.Exit(1)
	}

	// os.Args is Go's equivalent of PHP's $argv or Python's sys.argv.
	// os.Args[0] is the program name, os.Args[1:] are the arguments.
	// Here we check for a --fix flag to enable auto-correction mode.
	//
	// For more complex CLI argument parsing, you'd use the `flag` package
	// (like Python's argparse) or a third-party lib like cobra (like Laravel's
	// Artisan command signature parsing).
	// See: https://pkg.go.dev/os#pkg-variables (Args)
	// See: https://pkg.go.dev/flag — stdlib flag parsing
	autoFix := len(os.Args) > 1 && os.Args[1] == "--fix"

	// context.Background() provides a non-cancellable root context.
	// For a CLI tool like this, we don't need cancellation — the process
	// runs to completion or is killed. For long-running operations, you
	// might use signal.NotifyContext to handle Ctrl+C gracefully.
	discrepancies, err := jobs.ReconcileBalances(context.Background(), db, autoFix)
	if err != nil {
		slog.Error("reconciliation failed", "error", err)
		os.Exit(1)
	}

	if len(discrepancies) == 0 {
		fmt.Println("All account balances are consistent.")
		return
	}

	// fmt.Printf uses C-style format verbs — similar to PHP's sprintf:
	//   %d = integer, %s = string, %.2f = float with 2 decimals,
	//   %+.2f = float with explicit +/- sign, %-30s = left-padded string (30 chars wide)
	// See: https://pkg.go.dev/fmt#hdr-Printing
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
