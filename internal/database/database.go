// Package database handles PostgreSQL connection pooling and migrations.
//
// Laravel equivalent: config/database.php + the DB facade (Illuminate\Database\DatabaseManager).
// Django equivalent:  django.db.connections + settings.DATABASES configuration.
//
// In Laravel, you configure DB_HOST, DB_DATABASE, etc. in .env and the framework
// handles connection pooling behind the scenes via PDO. In Django, you set DATABASES
// in settings.py and the ORM manages connections per-request.
//
// Go's approach is different: you explicitly create a *sql.DB connection pool at
// startup and pass it to every layer that needs database access. There's no global
// facade or magic — you wire it yourself (dependency injection).
//
// Key Go concept — *sql.DB is NOT a single connection:
//   - It's a CONNECTION POOL that manages many connections automatically
//   - It's safe to share across goroutines (Go's lightweight threads)
//   - You create ONE *sql.DB at app startup and reuse it everywhere
//   - It opens/closes connections as needed, up to the configured limits
//
// See: https://pkg.go.dev/database/sql — the standard library database package
// See: https://go.dev/doc/database/manage-connections — official connection pool guide
package database

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	// Blank import (_ "package") — a Go pattern for side-effect-only imports.
	//
	// This import doesn't give us any usable name (hence the underscore _), but
	// the package's init() function runs on import and registers the "pgx" driver
	// with Go's database/sql registry. After this, sql.Open("pgx", ...) works.
	//
	// Laravel analogy: like adding a service provider to config/app.php — it
	// registers itself on boot so other parts of the app can use it.
	// Django analogy: like adding a database backend to settings.DATABASES['ENGINE'].
	//
	// Why pgx? It's the most performant and feature-rich PostgreSQL driver for Go.
	// The /stdlib sub-package provides compatibility with Go's database/sql interface.
	//
	// See: https://pkg.go.dev/github.com/jackc/pgx/v5/stdlib
	// See: https://pkg.go.dev/database/sql#Register — how driver registration works
	_ "github.com/jackc/pgx/v5/stdlib"
)

// Connect creates a connection pool to PostgreSQL and verifies it with a ping.
//
// Laravel equivalent: DB::connection('pgsql') — but explicit, not a facade.
// Django equivalent:  django.db.connections['default'] initialization.
//
// Go's database/sql package manages a pool of connections automatically.
// Unlike Laravel/Django where the framework handles this behind the scenes,
// in Go you configure the pool yourself and pass the *sql.DB around explicitly.
//
// Returns *sql.DB which is safe for concurrent use across goroutines —
// you typically create one pool at startup and pass it everywhere via
// constructor injection (not a global variable or facade).
//
// The returned *sql.DB should be closed with db.Close() when the app shuts down,
// typically via defer db.Close() in main().
func Connect(databaseURL string) (*sql.DB, error) {
	// sql.Open does NOT actually connect to the database!
	// It only validates the driver name ("pgx") and saves the connection string.
	// The real TCP connection happens lazily on first query/ping.
	//
	// Laravel equivalent: new PDO(...) — except PDO connects immediately,
	// while sql.Open is lazy. This is a common Go gotcha for newcomers.
	//
	// See: https://pkg.go.dev/database/sql#Open
	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("opening database: %w", err)
	}

	// Connection pool tuning — controls how the pool manages connections.
	//
	// Laravel equivalent: DB_POOL_SIZE in .env or the 'pool' config in database.php.
	// Django equivalent: CONN_MAX_AGE in settings.DATABASES (but Django's is simpler).
	//
	// MaxOpenConns: total connections allowed (active + idle). Like setting the pool
	//   size in Laravel Octane or Django with pgbouncer. Too low = queries queue up;
	//   too high = overwhelms the DB server.
	//
	// MaxIdleConns: connections kept open and ready for reuse. These avoid the cost
	//   of TCP handshake + auth on each query. Must be <= MaxOpenConns.
	//
	// ConnMaxLifetime: recycle connections after this duration. Prevents stale
	//   connections (e.g., if the DB server restarts). Similar to Django's CONN_MAX_AGE.
	//
	// See: https://go.dev/doc/database/manage-connections — official tuning guide
	db.SetMaxOpenConns(25)                 // max simultaneous connections
	db.SetMaxIdleConns(5)                  // keep 5 idle connections ready
	db.SetConnMaxLifetime(5 * time.Minute) // recycle connections after 5 min

	// PingContext verifies the database is actually reachable.
	// Since sql.Open is lazy, this is where the first real connection happens.
	//
	// context.WithTimeout creates a "deadline context" — if the ping doesn't
	// complete within 5 seconds, it's automatically cancelled and returns an error.
	//
	// Go concept — context.Context:
	//   Think of it as a "request scope" that carries deadlines and cancellation.
	//   Laravel equivalent: request timeout middleware.
	//   Django equivalent:  DATABASE_CONNECT_TIMEOUT or signal-based timeouts.
	//   Nearly every Go function that does I/O accepts a context as its first param.
	//
	// Go concept — defer:
	//   defer cancel() ensures the context's resources are freed when this function
	//   returns, regardless of whether we return early due to an error or succeed.
	//   Like a finally block in PHP try/catch, or Python's with statement.
	//
	// See: https://pkg.go.dev/context — the context package
	// See: https://pkg.go.dev/database/sql#DB.PingContext
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		// Clean up the pool if we can't connect — don't leak resources.
		db.Close()
		return nil, fmt.Errorf("pinging database: %w", err)
	}

	return db, nil
}
