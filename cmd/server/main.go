package main

import (
	"context"
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
	cfg := config.Load()

	// Database
	if cfg.DatabaseURL != "" {
		db, err := database.Connect(cfg.DatabaseURL)
		if err != nil {
			log.Fatalf("database connection: %v", err)
		}
		defer db.Close()
		log.Println("database connected")

		if err := database.RunMigrations(db); err != nil {
			log.Fatalf("migrations: %v", err)
		}
		log.Println("migrations complete")
	}

	r := handler.NewRouter()

	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      r,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Graceful shutdown
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	go func() {
		log.Printf("ClearMoney starting on :%s (env=%s)", cfg.Port, cfg.Env)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	<-ctx.Done()
	log.Println("shutting down...")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("shutdown error: %v", err)
	}
	log.Println("server stopped")
}
