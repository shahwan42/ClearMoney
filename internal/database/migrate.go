package database

import (
	"database/sql"
	"errors"
	"fmt"

	"github.com/golang-migrate/migrate/v4"
	"github.com/golang-migrate/migrate/v4/database/postgres"
	"github.com/golang-migrate/migrate/v4/source/iofs"

	"github.com/shahwan42/clearmoney/internal/database/migrations"
)

// RunMigrations applies all pending SQL migrations from the embedded filesystem.
//
// Laravel equivalent: php artisan migrate
// Django equivalent:  python manage.py migrate
//
// How it works:
//  1. Reads SQL migration files from the embedded filesystem (baked into the binary
//     at compile time — see migrations/migrations.go for the go:embed directive).
//  2. Checks the `schema_migrations` table to see which migrations have already run.
//     This is like Laravel's `migrations` table or Django's `django_migrations` table.
//  3. Applies any new migrations in sequential order (000001, 000002, ...).
//
// Migration file naming convention:
//   000001_create_institutions.up.sql   — the "up" migration (creates/alters)
//   000001_create_institutions.down.sql — the "down" migration (rollback)
//   This is similar to Laravel's up()/down() methods or Django's forwards/backwards.
//
// Key difference from Laravel/Django:
//   Migration files are embedded INTO the compiled binary using Go's embed package.
//   The binary is fully self-contained — no need to ship a migrations/ folder
//   alongside it in production. Laravel and Django read migration files from disk
//   at runtime, which means you must deploy the files alongside the app.
//
// We use the golang-migrate library (the most popular Go migration tool):
// See: https://github.com/golang-migrate/migrate — the migration library
// See: https://pkg.go.dev/github.com/golang-migrate/migrate/v4/source/iofs — embedded FS source
func RunMigrations(db *sql.DB) error {
	if db == nil {
		return fmt.Errorf("database connection is nil")
	}

	// Step 1: Create a migration source from the embedded SQL files.
	//
	// iofs.New wraps our embed.FS (defined in migrations/migrations.go) into
	// a source that golang-migrate can read from. The "." means read from the
	// root of the embedded filesystem.
	//
	// This is like telling Laravel/Django "here's where the migration files live"
	// — except instead of a disk path, it's a virtual filesystem compiled into the binary.
	//
	// See: https://pkg.go.dev/io/fs — Go's filesystem interface (used by iofs)
	source, err := iofs.New(migrations.FS, ".")
	if err != nil {
		return fmt.Errorf("creating migration source: %w", err)
	}

	// Step 2: Create a Postgres-specific database driver for golang-migrate.
	//
	// This driver knows how to:
	//   - Execute SQL statements against PostgreSQL
	//   - Create and query the `schema_migrations` table to track applied migrations
	//   - Handle database-level locking to prevent concurrent migration runs
	//
	// postgres.WithInstance reuses our existing *sql.DB connection pool rather than
	// opening a new connection. The empty &postgres.Config{} uses sensible defaults.
	driver, err := postgres.WithInstance(db, &postgres.Config{})
	if err != nil {
		return fmt.Errorf("creating migration driver: %w", err)
	}

	// Step 3: Combine source (where to read migrations) + driver (where to apply them).
	//
	// "iofs" is the source driver name, "clearmoney" is the database name.
	// This creates a Migrate instance that ties everything together.
	m, err := migrate.NewWithInstance("iofs", source, "clearmoney", driver)
	if err != nil {
		return fmt.Errorf("creating migrator: %w", err)
	}

	// Step 4: Apply all pending migrations.
	//
	// m.Up() runs all unapplied migrations in order (like artisan migrate --step=all).
	// If all migrations are already applied, it returns migrate.ErrNoChange — this
	// is NOT an error, just means the database schema is already up to date.
	//
	// Go concept — errors.Is():
	//   Checks if an error matches a specific sentinel error value, even if it's
	//   been wrapped. Like PHP's instanceof for exceptions but for Go's error values.
	//   See: https://pkg.go.dev/errors#Is
	//
	// Go concept — fmt.Errorf with %w:
	//   The %w verb wraps the original error inside a new one with added context.
	//   This preserves the error chain so callers can use errors.Is() to check
	//   the underlying cause. Similar to exception chaining in PHP (new Exception($msg, 0, $prev)).
	if err := m.Up(); err != nil && !errors.Is(err, migrate.ErrNoChange) {
		return fmt.Errorf("running migrations: %w", err)
	}

	return nil
}
