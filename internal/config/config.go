// Package config loads application settings from environment variables.
//
// This is similar to Laravel's config/ directory or Django's settings.py,
// but in Go we typically use a struct instead of a config array/dict.
//
// Laravel comparison:
//   - Laravel: config('app.env') reads from config/app.php which reads .env via env()
//   - Go: config.Load() reads directly from OS environment variables
//
// Django comparison:
//   - Django: settings.DEBUG = os.environ.get('DEBUG', 'True')
//   - Go: cfg.Env = getEnv("ENV", "development")
//
// Go does not have a built-in .env file loader. If you need .env support,
// use a library like github.com/joho/godotenv (the Go equivalent of vlucas/phpdotenv).
// For this project, env vars are set via docker-compose or the Makefile.
//
// See: https://pkg.go.dev/os#LookupEnv — the function we use under the hood
// See: https://12factor.net/config — the twelve-factor app methodology we follow
package config

import (
	"os"
	"strconv"
	"time"

	"github.com/shahwan42/clearmoney/internal/timeutil"
)

// Config holds all application-level configuration.
// In Go, we group related settings into a struct rather than using
// a global config dictionary like Laravel's config() helper.
//
// This is a plain struct (like a PHP class with public properties or a Python
// dataclass). Go has no constructor — you initialize structs with field literals
// (see Load below) or zero values (empty string for string, 0 for int, etc.).
type Config struct {
	Port            string // HTTP server port (default: "8080")
	DatabaseURL     string // PostgreSQL connection string (e.g. "postgres://user:pass@host:5432/db")
	Env             string // "development" or "production"
	LogLevel        string // slog level: "debug", "info", "warn", "error" (default: "info")
	VAPIDPublicKey  string         // VAPID public key for Web Push
	VAPIDPrivateKey string         // VAPID private key for Web Push
	Timezone        string         // IANA timezone name (default: "Africa/Cairo")
	Location        *time.Location // Parsed timezone location for date operations
	ResendAPIKey    string         // Resend API key for sending magic link emails
	EmailFrom       string         // Verified sender address (default: "noreply@clearmoney.app")
	AppURL          string         // Base URL for magic links (default: "http://localhost:8080")
	MaxDailyEmails  int            // Global daily email cap (default: 50, protects Resend free tier)
}

// Load reads config from environment variables with sensible defaults.
// Similar to Laravel's env() helper or Django's os.environ.get().
func Load() Config {
	tz := getEnv("APP_TIMEZONE", "Africa/Cairo")
	maxDaily := 50
	if v := getEnv("MAX_DAILY_EMAILS", ""); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			maxDaily = n
		}
	}

	return Config{
		Port:            getEnv("PORT", "8080"),
		DatabaseURL:     getEnv("DATABASE_URL", ""),
		Env:             getEnv("ENV", "development"),
		LogLevel:        getEnv("LOG_LEVEL", "info"),
		VAPIDPublicKey:  getEnv("VAPID_PUBLIC_KEY", ""),
		VAPIDPrivateKey: getEnv("VAPID_PRIVATE_KEY", ""),
		Timezone:        tz,
		Location:        timeutil.LoadLocation(tz),
		ResendAPIKey:    getEnv("RESEND_API_KEY", ""),
		EmailFrom:       getEnv("EMAIL_FROM", "noreply@clearmoney.app"),
		AppURL:          getEnv("APP_URL", "http://localhost:8080"),
		MaxDailyEmails:  maxDaily,
	}
}

// IsDevelopment returns true when running in development mode.
// The `(c Config)` part is a "method receiver" — it attaches this function to
// the Config type. It's like defining a method inside a PHP/Python class:
//   PHP:    public function isDevelopment(): bool { return $this->env === 'development'; }
//   Python: def is_development(self) -> bool: return self.env == 'development'
//   Go:     func (c Config) IsDevelopment() bool { return c.Env == "development" }
//
// Note: `c` is a value receiver (not a pointer `*Config`), meaning the method
// gets a copy of the struct. Since we only read fields, a copy is fine and
// avoids nil pointer risks. Use a pointer receiver when you need to mutate fields.
// See: https://go.dev/tour/methods/1
func (c Config) IsDevelopment() bool {
	return c.Env == "development"
}

// getEnv reads an environment variable or returns the fallback value.
//
// We use os.LookupEnv instead of os.Getenv because LookupEnv distinguishes
// between "variable is set to empty string" and "variable is not set at all":
//   - os.Getenv("FOO") returns "" in both cases — you can't tell the difference
//   - os.LookupEnv("FOO") returns (value, true) if set, ("", false) if unset
//
// The `val, ok` pattern is Go's "comma-ok idiom" — used extensively with maps,
// type assertions, and channel receives. It's like PHP's isset() check or
// Python's dict.get() with a default.
//
// Note: this is a lowercase (unexported) function — only visible within this
// package. In Go, capitalized names are public (exported), lowercase are private.
// This is like PHP's private/public or Python's _underscore convention, but enforced.
//
// See: https://pkg.go.dev/os#LookupEnv
func getEnv(key, fallback string) string {
	if val, ok := os.LookupEnv(key); ok {
		return val
	}
	return fallback
}
