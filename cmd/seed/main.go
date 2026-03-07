// Seed command populates the database with sample development data.
// Like Laravel's `php artisan db:seed` or Django's `manage.py loaddata`.
//
// Usage: go run ./cmd/seed
// Or: make seed
package main

import (
	"log"

	"github.com/ahmedelsamadisi/clearmoney/internal/config"
	"github.com/ahmedelsamadisi/clearmoney/internal/database"
	"github.com/ahmedelsamadisi/clearmoney/internal/database/seeds"
)

func main() {
	cfg := config.Load()

	db, err := database.Connect(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("connecting to database: %v", err)
	}
	defer db.Close()

	if err := database.RunMigrations(db); err != nil {
		log.Fatalf("running migrations: %v", err)
	}

	if err := seeds.Run(db); err != nil {
		log.Fatalf("seeding database: %v", err)
	}
}
