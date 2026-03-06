// Package database handles PostgreSQL connection pooling and migrations.
// Think of this as the equivalent of Laravel's database/DatabaseManager
// or Django's django.db.connections — it sets up and manages the DB connection pool.
package database

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	// The blank import (_ "...") registers the pgx driver with Go's database/sql.
	// This is a Go convention — the driver's init() function runs on import and
	// registers itself. Similar to how Laravel auto-discovers service providers.
	_ "github.com/jackc/pgx/v5/stdlib"
)

// Connect creates a connection pool to PostgreSQL and verifies it with a ping.
//
// Go's database/sql package manages a pool of connections automatically
// (similar to Laravel's connection pooling via the DB facade).
// We configure pool limits and then ping to ensure the DB is reachable.
//
// Returns *sql.DB which is safe for concurrent use across goroutines —
// you typically create one pool at startup and pass it everywhere.
func Connect(databaseURL string) (*sql.DB, error) {
	// sql.Open doesn't actually connect — it just validates the driver name
	// and saves the connection string. The real connection happens on first use.
	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("opening database: %w", err)
	}

	// Connection pool settings (similar to DB_POOL_SIZE in Laravel's .env)
	db.SetMaxOpenConns(25)          // max simultaneous connections
	db.SetMaxIdleConns(5)           // keep 5 idle connections ready
	db.SetConnMaxLifetime(5 * time.Minute) // recycle connections after 5 min

	// Ping verifies the connection actually works (with a 5-second timeout).
	// context.WithTimeout creates a deadline — if the ping doesn't complete
	// in time, it returns an error. defer cancel() cleans up the timer.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		db.Close()
		return nil, fmt.Errorf("pinging database: %w", err)
	}

	return db, nil
}
