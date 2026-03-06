// ClearMoney server entry point.
//
// This file is the equivalent of Laravel's public/index.php or Django's manage.py runserver.
// It wires everything together: config → database → router → HTTP server.
//
// In Go, the main() function is the program's entry point (no framework bootstrap).
// We explicitly set up each component, which gives full control over the lifecycle.
package main

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/config"
	"github.com/ahmedelsamadisi/clearmoney/internal/database"
	"github.com/ahmedelsamadisi/clearmoney/internal/handler"
)

func main() {
	// 1. Load configuration from environment variables
	cfg := config.Load()

	// 2. Connect to PostgreSQL and run migrations (if DATABASE_URL is set).
	// In development without Docker, you can run without a DB — the app
	// will start but database-dependent routes won't work.
	var db *sql.DB
	if cfg.DatabaseURL != "" {
		var err error
		db, err = database.Connect(cfg.DatabaseURL)
		if err != nil {
			log.Fatalf("database connection: %v", err)
		}
		defer db.Close() // defer = runs when main() exits (like PHP's register_shutdown_function)
		log.Println("database connected")

		if err := database.RunMigrations(db); err != nil {
			log.Fatalf("migrations: %v", err)
		}
		log.Println("migrations complete")
	}

	// 3. Create the HTTP router with all routes and middleware.
	// Pass db (may be nil) — router only registers DB routes when db != nil.
	r := handler.NewRouter(db)

	// 4. Configure the HTTP server with timeouts to prevent slow clients
	// from holding connections forever (a security best practice).
	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      r,
		ReadTimeout:  10 * time.Second,  // max time to read request
		WriteTimeout: 10 * time.Second,  // max time to write response
		IdleTimeout:  120 * time.Second, // max time for keep-alive connections
	}

	// 5. Graceful shutdown setup.
	// signal.NotifyContext listens for OS signals (Ctrl+C or docker stop).
	// When received, ctx.Done() triggers and we gracefully drain connections.
	// This is similar to Laravel Octane's graceful shutdown or Gunicorn's signal handling.
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	// Start the server in a goroutine (Go's lightweight thread).
	// This is non-blocking — main() continues to the <-ctx.Done() line below.
	go func() {
		log.Printf("ClearMoney starting on :%s (env=%s)", cfg.Port, cfg.Env)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	// Block here until we receive a shutdown signal
	<-ctx.Done()
	log.Println("shutting down...")

	// Give in-flight requests 5 seconds to complete before force-closing
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("shutdown error: %v", err)
	}
	log.Println("server stopped")
}
