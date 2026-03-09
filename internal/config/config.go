// Package config loads application settings from environment variables.
// This is similar to Laravel's config/ directory or Django's settings.py,
// but in Go we typically use a struct instead of a config array/dict.
package config

import "os"

// Config holds all application-level configuration.
// In Go, we group related settings into a struct rather than using
// a global config dictionary like Laravel's config() helper.
type Config struct {
	Port            string // HTTP server port (default: "8080")
	DatabaseURL     string // PostgreSQL connection string (e.g. "postgres://user:pass@host:5432/db")
	Env             string // "development" or "production"
	LogLevel        string // slog level: "debug", "info", "warn", "error" (default: "info")
	VAPIDPublicKey  string // VAPID public key for Web Push
	VAPIDPrivateKey string // VAPID private key for Web Push
}

// Load reads config from environment variables with sensible defaults.
// Similar to Laravel's env() helper or Django's os.environ.get().
func Load() Config {
	return Config{
		Port:            getEnv("PORT", "8080"),
		DatabaseURL:     getEnv("DATABASE_URL", ""),
		Env:             getEnv("ENV", "development"),
		LogLevel:        getEnv("LOG_LEVEL", "info"),
		VAPIDPublicKey:  getEnv("VAPID_PUBLIC_KEY", ""),
		VAPIDPrivateKey: getEnv("VAPID_PRIVATE_KEY", ""),
	}
}

// IsDevelopment returns true when running in development mode.
func (c Config) IsDevelopment() bool {
	return c.Env == "development"
}

// getEnv reads an environment variable or returns the fallback value.
func getEnv(key, fallback string) string {
	if val, ok := os.LookupEnv(key); ok {
		return val
	}
	return fallback
}
