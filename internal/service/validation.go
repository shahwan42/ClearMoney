package service

import (
	"fmt"
	"strings"
	"time"

	"github.com/shahwan42/clearmoney/internal/timeutil"
)

// requireTrimmedName trims whitespace from a name field and returns an error
// if the result is empty. Returns the trimmed string for assignment.
// Like a Laravel FormRequest rule ['name' => 'required|string'] with trim middleware.
func requireTrimmedName(value, fieldName string) (string, error) {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return "", fmt.Errorf("%s is required", fieldName)
	}
	return trimmed, nil
}

// requireNotEmpty returns an error if the string field is empty.
// Does not trim — use requireTrimmedName for user-facing name fields.
func requireNotEmpty(value, fieldName string) error {
	if value == "" {
		return fmt.Errorf("%s is required", fieldName)
	}
	return nil
}

// requirePositive returns an error if the float64 value is zero or negative.
func requirePositive(value float64, fieldName string) error {
	if value <= 0 {
		return fmt.Errorf("%s must be positive", fieldName)
	}
	return nil
}

// requirePositiveInt returns an error if the int value is zero or negative.
func requirePositiveInt(value int, fieldName string) error {
	if value <= 0 {
		return fmt.Errorf("%s must be positive", fieldName)
	}
	return nil
}

// defaultDate returns the given date if non-zero, or the current UTC time otherwise.
func defaultDate(d time.Time) time.Time {
	if d.IsZero() {
		return timeutil.Now()
	}
	return d
}
