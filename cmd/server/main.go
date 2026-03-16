// ClearMoney server entry point.
//
// This file is the equivalent of Laravel's public/index.php or Django's manage.py runserver.
// It wires everything together: config → database → router → HTTP server.
//
// In Go, the main() function is the program's entry point (no framework bootstrap).
// We explicitly set up each component, which gives full control over the lifecycle.
//
// Key Go concepts in this file:
//   - goroutines: lightweight concurrent functions (like PHP fibers or Python asyncio tasks)
//   - defer: schedule cleanup to run when the enclosing function returns
//   - context: carries deadlines, cancellation signals, and request-scoped values
//   - channels (<-): used to communicate between goroutines (like Python's queue.Queue)
//   - signal handling: OS-level process signals (SIGINT=Ctrl+C, SIGTERM=docker stop)
//
// See: https://pkg.go.dev/log/slog — Go's structured logging (replaces log.Printf)
// See: https://pkg.go.dev/context — request-scoped values, cancellation, and deadlines
// See: https://pkg.go.dev/os/signal — OS signal handling for graceful shutdown
package main

import (
	"context"
	"database/sql"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/shahwan42/clearmoney/internal/config"
	"github.com/shahwan42/clearmoney/internal/database"
	"github.com/shahwan42/clearmoney/internal/handler"
	"github.com/shahwan42/clearmoney/internal/jobs"
	"github.com/shahwan42/clearmoney/internal/repository"
	"github.com/shahwan42/clearmoney/internal/service"
)

func main() {
	// 1. Load configuration from environment variables
	cfg := config.Load()

	// Configure structured logging (log/slog) with level from LOG_LEVEL env var.
	// slog is Go 1.21+'s built-in structured logger — similar to Laravel's Log facade
	// or Python's logging module. It outputs key=value pairs instead of plain text,
	// making logs easier to search in production (e.g., grep by "error" key).
	//
	// Levels: debug, info, warn, error (default: info).
	// See: https://pkg.go.dev/log/slog#Level
	var logLevel slog.Level
	switch strings.ToLower(cfg.LogLevel) {
	case "debug":
		logLevel = slog.LevelDebug
	case "warn":
		logLevel = slog.LevelWarn
	case "error":
		logLevel = slog.LevelError
	default:
		logLevel = slog.LevelInfo
	}
	// slog.SetDefault replaces the global logger, so all slog.Info/Warn/Error calls
	// use this handler. TextHandler writes human-readable logs to stderr.
	// In production, you might swap to slog.NewJSONHandler for machine-parseable output.
	// See: https://pkg.go.dev/log/slog#SetDefault
	slog.SetDefault(slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: logLevel})))

	// 2. Connect to PostgreSQL and run migrations (if DATABASE_URL is set).
	// In development without Docker, you can run without a DB — the app
	// will start but database-dependent routes won't work.
	var db *sql.DB
	if cfg.DatabaseURL != "" {
		var err error
		db, err = database.Connect(cfg.DatabaseURL)
		if err != nil {
			slog.Error("database connection failed", "error", err)
			os.Exit(1)
		}
		// defer schedules db.Close() to run when main() returns — like PHP's
		// register_shutdown_function or Python's atexit. Multiple defers execute
		// in LIFO order (last deferred = first executed). This ensures the DB
		// connection is always closed, even if the function exits early via os.Exit.
		// See: https://go.dev/tour/flowcontrol/12
		defer db.Close()
		slog.Info("database connected")

		if err := database.RunMigrations(db); err != nil {
			slog.Error("migrations failed", "error", err)
			os.Exit(1)
		}
		slog.Info("migrations complete")

		// Process any due recurring rules on startup for all users.
		userRepo := repository.NewUserRepo(db)
		recurringRepo := repository.NewRecurringRepo(db)
		txRepo := repository.NewTransactionRepo(db)
		accountRepo := repository.NewAccountRepo(db)
		txSvc := service.NewTransactionService(txRepo, accountRepo)
		recurringSvc := service.NewRecurringService(recurringRepo, txSvc)
		recurringSvc.SetTimezone(cfg.Location)

		userIDs, err := userRepo.GetAllIDs(context.Background())
		if err != nil {
			slog.Warn("failed to list users for recurring rules", "error", err)
		} else {
			for _, uid := range userIDs {
				processed, err := recurringSvc.ProcessDueRules(context.Background(), uid)
				if err != nil {
					slog.Warn("recurring rules processing error", "user_id", uid, "error", err)
				} else if processed > 0 {
					slog.Info("recurring: auto-created transactions", "user_id", uid, "count", processed)
				}
			}
		}

		// Run balance reconciliation on startup (report only, no auto-fix).
		discrepancies, err := jobs.ReconcileBalances(context.Background(), db, false)
		if err != nil {
			slog.Warn("reconciliation error", "error", err)
		} else if len(discrepancies) > 0 {
			slog.Warn("balance discrepancies found", "count", len(discrepancies))
			for _, d := range discrepancies {
				slog.Warn("balance discrepancy",
					"account", d.AccountName,
					"cached", d.CachedBalance,
					"expected", d.ExpectedBalance,
					"diff", d.Difference,
				)
			}
		}

		// Refresh materialized views on startup for fresh data.
		if err := jobs.RefreshMaterializedViews(context.Background(), db); err != nil {
			slog.Warn("materialized view refresh error", "error", err)
		}

		// Take daily balance snapshots (for sparklines and trend indicators).
		// Also backfills up to 90 missing days using transaction history.
		backfilled, err := jobs.TakeSnapshots(context.Background(), db, cfg.Location)
		if err != nil {
			slog.Warn("snapshot error", "error", err)
		} else if backfilled > 0 {
			slog.Info("snapshots: backfilled days", "count", backfilled)
		}
	}

	// 3. Create the HTTP router with all routes and middleware.
	// Pass db (may be nil) — router only registers DB routes when db != nil.
	r := handler.NewRouter(db, cfg.Location, cfg)

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
	// signal.NotifyContext creates a context that is automatically cancelled when the
	// process receives SIGINT (Ctrl+C) or SIGTERM (docker stop / kill).
	// This is similar to Laravel Octane's graceful shutdown or Gunicorn's signal handling.
	//
	// How it works:
	//   - ctx is a context.Context — it has a Done() channel that closes on signal
	//   - stop is a cleanup function to release signal-catching resources
	//   - <-ctx.Done() blocks until a signal arrives (the <- operator reads from a channel)
	//
	// In Laravel/Django, the web server (Apache/Nginx/Gunicorn) handles this for you.
	// In Go, since we ARE the server, we must handle signals ourselves.
	// See: https://pkg.go.dev/os/signal#NotifyContext
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	// Start the server in a goroutine (Go's lightweight thread).
	// A goroutine is like a PHP fiber or Python coroutine, but managed by Go's runtime.
	// The `go` keyword launches the function concurrently — main() does NOT wait for it.
	// Instead, main() continues to the <-ctx.Done() line below, which blocks until shutdown.
	//
	// Why a goroutine? ListenAndServe blocks forever (it's the event loop). We need
	// main() to also listen for shutdown signals, so we run the server concurrently.
	// See: https://go.dev/tour/concurrency/1
	go func() {
		slog.Info("ClearMoney starting", "port", cfg.Port, "env", cfg.Env)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server error", "error", err)
			os.Exit(1)
		}
	}()

	// Block here until we receive a shutdown signal.
	// The <- operator receives from a channel. ctx.Done() returns a channel that
	// closes when the context is cancelled (i.e., when SIGINT/SIGTERM arrives).
	// This is Go's idiomatic way to "wait for something" — no polling, no sleep loops.
	// See: https://pkg.go.dev/context#Context (Done method)
	<-ctx.Done()
	slog.Info("shutting down...")

	// Give in-flight requests 5 seconds to complete before force-closing.
	// context.WithTimeout creates a child context that auto-cancels after the deadline.
	// cancel() must always be called (via defer) to release the timer resources — the
	// Go linter (and `go vet`) will warn if you forget this.
	// See: https://pkg.go.dev/context#WithTimeout
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		slog.Error("shutdown error", "error", err)
		os.Exit(1)
	}
	slog.Info("server stopped")
}
