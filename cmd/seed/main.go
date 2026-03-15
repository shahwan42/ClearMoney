// Seed command populates the database with sample development data.
// Like Laravel's `php artisan db:seed` or Django's `manage.py loaddata`.
//
// In Laravel, seeders live in database/seeders/ and are PHP classes. In Go,
// we use a simple Run(db) function in internal/database/seeds/ that executes
// raw SQL inserts. The effect is the same: populate tables with test data.
//
// Usage:
//
//	go run ./cmd/seed
//	make seed
package main

import (
	"log/slog"
	"os"

	"github.com/shahwan42/clearmoney/internal/config"
	"github.com/shahwan42/clearmoney/internal/database"
	"github.com/shahwan42/clearmoney/internal/database/seeds"
)

func main() {
	// Load config from environment — see internal/config/config.go for details.
	cfg := config.Load()

	db, err := database.Connect(cfg.DatabaseURL)
	if err != nil {
		// slog.Error + os.Exit(1) replaces the old log.Fatalf pattern.
		// slog gives structured key=value output; log.Fatalf gives plain text.
		// We use slog consistently across all cmd/ binaries for uniform log format.
		slog.Error("connecting to database", "error", err)
		os.Exit(1)
	}
	defer db.Close()

	if err := database.RunMigrations(db); err != nil {
		slog.Error("running migrations", "error", err)
		os.Exit(1)
	}

	if err := seeds.Run(db); err != nil {
		slog.Error("seeding database", "error", err)
		os.Exit(1)
	}

	slog.Info("database seeded successfully")
}
