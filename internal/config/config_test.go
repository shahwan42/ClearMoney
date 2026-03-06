package config

import (
	"os"
	"testing"
)

func TestLoad_Defaults(t *testing.T) {
	// Unset any env vars that might interfere
	os.Unsetenv("PORT")
	os.Unsetenv("DATABASE_URL")
	os.Unsetenv("ENV")

	cfg := Load()

	if cfg.Port != "8080" {
		t.Errorf("expected default port 8080, got %s", cfg.Port)
	}
	if cfg.Env != "development" {
		t.Errorf("expected default env development, got %s", cfg.Env)
	}
	if cfg.DatabaseURL != "" {
		t.Errorf("expected empty database URL by default, got %s", cfg.DatabaseURL)
	}
}

func TestLoad_FromEnv(t *testing.T) {
	os.Setenv("PORT", "9090")
	os.Setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/clearmoney")
	os.Setenv("ENV", "production")
	defer func() {
		os.Unsetenv("PORT")
		os.Unsetenv("DATABASE_URL")
		os.Unsetenv("ENV")
	}()

	cfg := Load()

	if cfg.Port != "9090" {
		t.Errorf("expected port 9090, got %s", cfg.Port)
	}
	if cfg.DatabaseURL != "postgres://user:pass@localhost:5432/clearmoney" {
		t.Errorf("expected database URL from env, got %s", cfg.DatabaseURL)
	}
	if cfg.Env != "production" {
		t.Errorf("expected env production, got %s", cfg.Env)
	}
}

func TestConfig_IsDevelopment(t *testing.T) {
	cfg := Config{Env: "development"}
	if !cfg.IsDevelopment() {
		t.Error("expected IsDevelopment to return true")
	}

	cfg.Env = "production"
	if cfg.IsDevelopment() {
		t.Error("expected IsDevelopment to return false")
	}
}
