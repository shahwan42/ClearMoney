package database

import (
	"database/sql"
	"errors"
	"fmt"

	"github.com/golang-migrate/migrate/v4"
	"github.com/golang-migrate/migrate/v4/database/postgres"
	"github.com/golang-migrate/migrate/v4/source/iofs"

	"github.com/ahmedelsamadisi/clearmoney/internal/database/migrations"
)

// RunMigrations applies all pending SQL migrations from the embedded filesystem.
//
// This is equivalent to running `php artisan migrate` in Laravel or
// `python manage.py migrate` in Django — it checks which migrations have
// already been applied (tracked in a `schema_migrations` table) and runs
// any new ones in order.
//
// Migration files are embedded into the Go binary at compile time using
// Go's embed package (see migrations/migrations.go). This means the binary
// is fully self-contained — no need to ship migration files separately.
func RunMigrations(db *sql.DB) error {
	if db == nil {
		return fmt.Errorf("database connection is nil")
	}

	// Create a migration source from the embedded SQL files.
	// iofs.New reads from the embed.FS defined in migrations/migrations.go.
	source, err := iofs.New(migrations.FS, ".")
	if err != nil {
		return fmt.Errorf("creating migration source: %w", err)
	}

	// Create a Postgres-specific driver that knows how to execute SQL
	// and track migration state in the schema_migrations table.
	driver, err := postgres.WithInstance(db, &postgres.Config{})
	if err != nil {
		return fmt.Errorf("creating migration driver: %w", err)
	}

	// Combine source + driver into a migrator instance.
	m, err := migrate.NewWithInstance("iofs", source, "clearmoney", driver)
	if err != nil {
		return fmt.Errorf("creating migrator: %w", err)
	}

	// Run all pending migrations. ErrNoChange means everything is already
	// up to date — that's fine, not an error.
	if err := m.Up(); err != nil && !errors.Is(err, migrate.ErrNoChange) {
		return fmt.Errorf("running migrations: %w", err)
	}

	return nil
}
