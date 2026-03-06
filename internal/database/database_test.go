package database

import (
	"context"
	"os"
	"testing"
	"time"
)

func getTestDatabaseURL(t *testing.T) string {
	t.Helper()
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("TEST_DATABASE_URL not set, skipping integration test")
	}
	return url
}

func TestConnect_Success(t *testing.T) {
	url := getTestDatabaseURL(t)

	db, err := Connect(url)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	defer db.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		t.Fatalf("expected ping to succeed, got %v", err)
	}
}

func TestConnect_InvalidURL(t *testing.T) {
	_, err := Connect("postgres://invalid:invalid@localhost:9999/nonexistent?sslmode=disable&connect_timeout=1")
	if err == nil {
		t.Fatal("expected error for invalid connection, got nil")
	}
}
